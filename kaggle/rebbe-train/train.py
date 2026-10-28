"""The Rebbe model: Whisper large-v3-turbo taught the Rebbe's Yiddish (runs on Kaggle's GPU, pushed by rebbe-train.yml).

2026-10-28 (the owner: "Go ahead, let's train this"; Kaggle free GPU; own use only — this kernel, its dataset
and its output stay private). The data: the private Kaggle dataset rebbe-yiddish-speech (scripts/rebbe_dataset.py):
train/ and dev/ = clips of the Rebbe with Claude's curated ✓ text, test/ = the Lexicon clips (verbatim, never
trained on). LoRA on attention and MLP of encoder and decoder; the stock model and the trained one are measured
on dev and test (character error rate, letters only). Output (/kaggle/working): the model for faster-whisper /
WhisperX (CTranslate2, int8), the LoRA adapter, metrics.json and samples.txt.
"""
import glob
import json
import os
import re
import subprocess
import sys
import time

subprocess.run([sys.executable, '-m', 'pip', 'install', '-q', 'transformers>=4.44,<5', 'peft>=0.12', 'accelerate',
                'jiwer', 'soundfile', 'ctranslate2'], check=True)

import jiwer  # noqa: E402
import soundfile as sf  # noqa: E402
import torch  # noqa: E402
from peft import LoraConfig, get_peft_model  # noqa: E402
from transformers import (Seq2SeqTrainer, Seq2SeqTrainingArguments, WhisperForConditionalGeneration,  # noqa: E402
                          WhisperProcessor)

BASE = 'openai/whisper-large-v3-turbo'
OUT = '/kaggle/working'
EPOCHS = float(os.environ.get('EPOCHS', 3))
LR = float(os.environ.get('LR', 5e-4))
DATA = next((d for d in glob.glob('/kaggle/input/**/train/metadata.jsonl', recursive=True)), None)
if not DATA:
    raise SystemExit('the dataset rebbe-yiddish-speech is not attached')
ROOT = os.path.dirname(os.path.dirname(DATA))
print('data:', ROOT, '· GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'none')


def rows(split):
    p = os.path.join(ROOT, split, 'metadata.jsonl')
    if not os.path.exists(p):
        return []
    out = [json.loads(l) for l in open(p, encoding='utf8') if l.strip()]
    for r in out:
        r['path'] = os.path.join(ROOT, split, r['file_name'])
    return out


train, dev, test = rows('train'), rows('dev'), rows('test')
print(f'train {len(train)} ({sum(r.get("duration", 0) for r in train) / 3600:.2f} h) · dev {len(dev)} · test {len(test)}')

proc = WhisperProcessor.from_pretrained(BASE, language='yiddish', task='transcribe')
model = WhisperForConditionalGeneration.from_pretrained(BASE, torch_dtype=torch.float16).to('cuda')
model.generation_config.language = 'yiddish'
model.generation_config.task = 'transcribe'
model.generation_config.forced_decoder_ids = None


def audio(path):
    x, sr = sf.read(path, dtype='float32')
    if x.ndim > 1:
        x = x.mean(axis=1)
    assert sr == 16000, f'{path}: {sr} Hz'
    return x


def norm(t):
    t = re.sub(r'[֑-ׇ]', '', t)       # niqqud and the Yiddish points (אַ = א for scoring)
    t = re.sub(r'[^א-ת\s]', ' ', t)   # letters only
    return re.sub(r'\s+', ' ', t).strip()


def transcribe(m, items, bs=8):
    m.eval()
    hyps = []
    for i in range(0, len(items), bs):
        batch = items[i:i + bs]
        feats = proc.feature_extractor([audio(r['path']) for r in batch], sampling_rate=16000, return_tensors='pt')
        with torch.inference_mode(), torch.autocast('cuda', dtype=torch.float16):
            ids = m.generate(feats.input_features.to('cuda', torch.float16), language='yiddish', task='transcribe',
                             max_new_tokens=220)
        hyps += proc.batch_decode(ids, skip_special_tokens=True)
    return hyps


def score(m, items, name):
    if not items:
        return None
    hyps = transcribe(m, items)
    refs = [norm(r['text']) for r in items]
    pairs = [(r, norm(h)) for r, h in zip(refs, hyps) if r]
    cer = jiwer.cer([p[0] for p in pairs], [p[1] for p in pairs])
    wer = jiwer.wer([p[0] for p in pairs], [p[1] for p in pairs])
    print(f'{name}: CER {cer:.3f} · WER {wer:.3f} ({len(pairs)} clips)')
    return {'cer': round(cer, 4), 'wer': round(wer, 4), 'clips': len(pairs), 'hyps': hyps}


metrics = {'base': BASE, 'train_examples': len(train), 'epochs': EPOCHS, 'lr': LR}
t0 = time.time()
metrics['stock'] = {k: score(model, v, f'stock {k}') for k, v in (('dev', dev), ('test', test))}

# LoRA training (fp32 master weights for the adapter; the base stays fp16)
model = WhisperForConditionalGeneration.from_pretrained(BASE, torch_dtype=torch.float32)
model.config.forced_decoder_ids = None
model.config.suppress_tokens = []
model.generation_config.language = 'yiddish'
model.generation_config.task = 'transcribe'
lora = LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, bias='none',
                  target_modules=['q_proj', 'k_proj', 'v_proj', 'out_proj', 'fc1', 'fc2'])
model = get_peft_model(model, lora)
model.print_trainable_parameters()


class Clips(torch.utils.data.Dataset):
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        r = self.items[i]
        feats = proc.feature_extractor(audio(r['path']), sampling_rate=16000).input_features[0]
        labels = proc.tokenizer(r['text']).input_ids[:440]
        return {'input_features': feats, 'labels': labels}


def collate(batch):
    feats = proc.feature_extractor.pad([{'input_features': b['input_features']} for b in batch], return_tensors='pt')
    lab = proc.tokenizer.pad([{'input_ids': b['labels']} for b in batch], return_tensors='pt')
    labels = lab['input_ids'].masked_fill(lab['attention_mask'].ne(1), -100)
    if (labels[:, 0] == model.config.decoder_start_token_id).all():
        labels = labels[:, 1:]
    return {'input_features': feats['input_features'], 'labels': labels}


args = Seq2SeqTrainingArguments(
    output_dir=f'{OUT}/ckpt', per_device_train_batch_size=4, gradient_accumulation_steps=4, learning_rate=LR,
    warmup_ratio=0.05, num_train_epochs=EPOCHS, fp16=True, gradient_checkpointing=True,
    gradient_checkpointing_kwargs={'use_reentrant': False}, logging_steps=20, save_strategy='no',
    eval_strategy='epoch' if dev else 'no', per_device_eval_batch_size=4, report_to=[], remove_unused_columns=False,
    label_names=['labels'], dataloader_num_workers=2)
trainer = Seq2SeqTrainer(model=model, args=args, train_dataset=Clips(train), eval_dataset=Clips(dev) if dev else None,
                         data_collator=collate)
trainer.train()
model.save_pretrained(f'{OUT}/lora')
metrics['train_log'] = trainer.state.log_history

merged = model.merge_and_unload().half().to('cuda')
metrics['trained'] = {k: score(merged, v, f'trained {k}') for k, v in (('dev', dev), ('test', test))}
metrics['minutes'] = round((time.time() - t0) / 60)

with open(f'{OUT}/samples.txt', 'w', encoding='utf8') as f:
    for k, items in (('test', test), ('dev', dev[:40])):
        st, tr = metrics['stock'].get(k), metrics['trained'].get(k)
        if not st:
            continue
        for i, r in enumerate(items[:len(tr['hyps'])]):
            f.write(f'[{k}] {r["file_name"]}\n  ref:     {r["text"]}\n  stock:   {st["hyps"][i]}\n  trained: {tr["hyps"][i]}\n\n')
for side in ('stock', 'trained'):
    for v in metrics[side].values():
        if v:
            v.pop('hyps', None)
json.dump(metrics, open(f'{OUT}/metrics.json', 'w'), indent=1, default=str)
print(json.dumps({k: metrics[k] for k in ('stock', 'trained', 'minutes')}, indent=1))

# for faster-whisper / WhisperX (the next round of ears): CTranslate2, int8
merged.save_pretrained(f'{OUT}/merged')
proc.save_pretrained(f'{OUT}/merged')
subprocess.run(['ct2-transformers-converter', '--model', f'{OUT}/merged', '--output_dir', f'{OUT}/rebbe-whisper-ct2',
                '--quantization', 'int8_float16', '--copy_files', 'tokenizer.json', 'preprocessor_config.json'], check=True)
subprocess.run(['rm', '-rf', f'{OUT}/merged', f'{OUT}/ckpt'])
print('done:', os.listdir(OUT))
