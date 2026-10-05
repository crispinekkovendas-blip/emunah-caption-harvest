/**
 * parashiot.ts
 * Complete lookup table of all 54 weekly Torah portions.
 * Verbatim TypeScript port of src/data/parashiot.js from the Next.js repo.
 */

// ─── Types ─────────────────────────────────────────────────────────────────
export interface BookInfo {
  key: string
  namePt: string
  trad: string
  gradient: string
}

export interface Parasha {
  key: string
  name: string
  hebrewName: string
  traducao: string
  book: string
  tora: string
  haftara: string
  brit: string
  tehilim: string
  hebcalNames: string[]
  resumo: string
  temas: string[]
}

// ─── 5 Books ───────────────────────────────────────────────────────────────
export const BOOKS: BookInfo[] = [
  { key: 'bereshit', namePt: 'Bereshit', trad: 'Gênesis',       gradient: 'linear-gradient(135deg, #d9d6cf 0%, #e6e3dc 55%, #efece5 100%)' },
  { key: 'shemot',   namePt: 'Shemot',   trad: 'Êxodo',         gradient: 'linear-gradient(135deg, #cfccc5 0%, #ddd9d2 55%, #e9e6df 100%)' },
  { key: 'vayicra',  namePt: 'Vayicrá',  trad: 'Levítico',      gradient: 'linear-gradient(135deg, #e2dfd8 0%, #ebe8e1 55%, #f2efe9 100%)' },
  { key: 'bamidbar', namePt: 'Bamidbar', trad: 'Números',       gradient: 'linear-gradient(135deg, #d3d0c9 0%, #e0ddd6 55%, #ebe8e1 100%)' },
  { key: 'devarim',  namePt: 'Devarim',  trad: 'Deuteronômio',  gradient: 'linear-gradient(135deg, #c9c6bf 0%, #d8d5ce 55%, #e5e2db 100%)' },
]

export function getBookInfo(bookKey: string | undefined): BookInfo {
  return BOOKS.find(b => b.key === bookKey) ?? BOOKS[0]!
}

// ─── All 54 Parashiot ──────────────────────────────────────────────────────
export const parashiot: Parasha[] = [

  // ── BERESHIT / Gênesis ──────────────────────────────────────────────────
  {
    key: 'bereshit', name: 'Bereshit', hebrewName: 'בְּרֵאשִׁית',
    traducao: 'No Princípio', book: 'bereshit',
    tora: 'GN 1:1–6:8', haftara: 'IS 42:5-21', brit: 'JO 1:1-5', tehilim: '139',
    hebcalNames: ['Bereshit', 'Bereishit', 'Beresheet'],
    resumo: 'Deus cria o universo em seis dias e descansa no sétimo. Adão e Chavá são colocados no Jardim do Éden, mas desobedecem ao comer do fruto proibido e são expulsos. Caim mata seu irmão Hêvel, e a humanidade começa a se multiplicar — mas também a se corromper.',
    temas: ['Criação', 'Livre-arbítrio', 'Consequência do pecado'],
  },
  {
    key: 'noach', name: 'Noach', hebrewName: 'נֹחַ',
    traducao: 'Noé', book: 'bereshit',
    tora: 'GN 6:9–11:32', haftara: 'IS 54:1-10', brit: 'I PE 3:18-22', tehilim: '29',
    hebcalNames: ['Noach', 'Noah'],
    resumo: 'A humanidade se corrompeu e Deus decide enviar o dilúvio, salvando apenas Noach e sua família na arca. Após as águas baixarem, Deus estabelece o arco-íris como sinal de aliança. A humanidade tenta construir a Torre de Babel, e Deus confunde as línguas.',
    temas: ['Juízo divino', 'Aliança', 'Recomeço'],
  },
  {
    key: 'lech-lecha', name: 'Lech-Lecha', hebrewName: 'לֶךְ לְךָ',
    traducao: 'Vai por Ti', book: 'bereshit',
    tora: 'GN 12:1–17:27', haftara: 'IS 40:27-41:16', brit: 'RM 4:1-25', tehilim: '110',
    hebcalNames: ['Lech-Lecha', 'Lech Lecha'],
    resumo: 'Deus chama Avram para deixar sua terra e ir à terra de Canaã, prometendo fazer dele uma grande nação. Avram e Sarai enfrentam fome, conflitos e a espera por um filho. Deus muda seus nomes para Avraham e Sará, e institui a brit milá como sinal da aliança.',
    temas: ['Fé', 'Chamado divino', 'Aliança de Avraham'],
  },
  {
    key: 'vayera', name: 'Vayera', hebrewName: 'וַיֵּרָא',
    traducao: 'E Apareceu', book: 'bereshit',
    tora: 'GN 18:1–22:24', haftara: 'II RS 4:1-23', brit: 'II PE 2:4-11', tehilim: '11',
    hebcalNames: ['Vayera'],
    resumo: 'Três anjos visitam Avraham e anunciam o nascimento de Yitzchak. Deus decide destruir Sedom e Amorá, e Avraham intercede. Lot é salvo, mas sua esposa vira uma estátua de sal. Nasce Yitzchak, e a grande prova vem com a Akedá — o sacrifício de Yitzchak.',
    temas: ['Hospitalidade', 'Justiça divina', 'Prova de fé'],
  },
  {
    key: 'chayei-sarah', name: 'Chayei Sarah', hebrewName: 'חַיֵּי שָׂרָה',
    traducao: 'Viveu Sará', book: 'bereshit',
    tora: 'GN 23:01–25:18', haftara: 'I RS 1:1-31', brit: 'I CO 15:50-57', tehilim: '45',
    hebcalNames: ['Chayei Sara', 'Chayei Sarah'],
    resumo: 'Sará falece aos 127 anos e Avraham adquire a caverna de Machpelá em Chevron para sepultá-la. O servo Eliézer viaja para encontrar uma esposa para Yitzchak e, por meio de sinais divinos, encontra Rivká. Avraham se casa novamente e falece.',
    temas: ['Luto e honra', 'Providência divina', 'Casamento'],
  },
  {
    key: 'toldot', name: 'Toldot', hebrewName: 'תּוֹלְדוֹת',
    traducao: 'Gerações', book: 'bereshit',
    tora: 'GN 25:19–28:09', haftara: 'ML 1:1-2:7', brit: 'RM 9:6-13', tehilim: '36',
    hebcalNames: ['Toldot'],
    resumo: 'Nascem os gêmeos Essav e Yaacov. Essav vende sua primogenitura por um prato de lentilhas. Yitzchak abençoa Yaacov pensando ser Essav, e Yaacov foge para a casa de Lavan para escapar da ira de seu irmão.',
    temas: ['Destino', 'Primogenitura', 'Bênção'],
  },
  {
    key: 'vayetzei', name: 'Vayetzei', hebrewName: 'וַיֵּצֵא',
    traducao: 'E Saiu', book: 'bereshit',
    tora: 'GN 28:10–32:03', haftara: 'OS 12:13-14:10', brit: 'JO 1:43-51', tehilim: '3',
    hebcalNames: ['Vayetzei', 'Vayeitzei'],
    resumo: 'Yaacov sonha com a escada que liga o céu e a terra. Chega à casa de Lavan, trabalha sete anos por Rachel, mas recebe Leá. Trabalha mais sete anos por Rachel. Nascem onze dos doze filhos de Israel. Yaacov enriquece e parte de volta para Canaã.',
    temas: ['Sonhos proféticos', 'Trabalho e perseverança', 'As tribos de Israel'],
  },
  {
    key: 'vayishlach', name: 'Vayishlach', hebrewName: 'וַיִּשְׁלַח',
    traducao: 'E Enviou', book: 'bereshit',
    tora: 'GN 32:04–36:43', haftara: 'OS 11:7-12:12', brit: 'MT 26:36-46', tehilim: '140',
    hebcalNames: ['Vayishlach'],
    resumo: 'Yaacov se prepara para reencontrar Essav e luta com um anjo durante a noite, recebendo o nome Israel — "lutou com Deus". Os irmãos se reconciliam. O incidente de Diná em Shechem, e Rachel falece ao dar à luz Binyamin.',
    temas: ['Confronto espiritual', 'Transformação', 'Reconciliação'],
  },
  {
    key: 'vayeshev', name: 'Vayeshev', hebrewName: 'וַיֵּשֶׁב',
    traducao: 'E Assentou-se', book: 'bereshit',
    tora: 'GN 37:1–40:23', haftara: 'AM 2:06-3:08', brit: 'AT 7:9-16', tehilim: '112',
    hebcalNames: ['Vayeshev'],
    resumo: 'Yossef é o filho favorito de Yaacov e recebe uma túnica especial. Seus irmãos, com ciúmes, vendem-no como escravo para o Egito. Na casa de Potifar, Yossef é caluniado e preso. Na prisão, interpreta os sonhos do copeiro e do padeiro do faraó.',
    temas: ['Ciúme', 'Exílio', 'Providência oculta'],
  },
  {
    key: 'miketz', name: 'Miketz', hebrewName: 'מִקֵּץ',
    traducao: 'No Fim', book: 'bereshit',
    tora: 'GN 41:1–44:17', haftara: 'I RS 3:15-4:1', brit: 'I CO 2:1-5', tehilim: '40',
    hebcalNames: ['Miketz'],
    resumo: 'Faraó sonha com vacas e espigas, e Yossef interpreta: sete anos de fartura seguidos de sete de fome. Yossef é nomeado vice-rei do Egito. Seus irmãos descem ao Egito para comprar alimentos, sem reconhecê-lo. Yossef os testa.',
    temas: ['Interpretação de sonhos', 'Ascensão ao poder', 'Teste'],
  },
  {
    key: 'vayigash', name: 'Vayigash', hebrewName: 'וַיִּגַּשׁ',
    traducao: 'E Apegou-se', book: 'bereshit',
    tora: 'GN 44:18–47:27', haftara: 'EZ 37:15-28', brit: 'LC 6:9-16', tehilim: '48',
    hebcalNames: ['Vayigash'],
    resumo: 'Yehudá faz um discurso apaixonado em defesa de Binyamin. Yossef se revela aos seus irmãos em uma cena emocionante de reconciliação. Yaacov desce ao Egito com toda a família — setenta almas — e reencontra Yossef após 22 anos.',
    temas: ['Reconciliação', 'Coragem moral', 'Reunião familiar'],
  },
  {
    key: 'vayechi', name: 'Vayechi', hebrewName: 'וַיְחִי',
    traducao: 'E Foi', book: 'bereshit',
    tora: 'GN 47:28–50:26', haftara: 'I RS 2:1-12', brit: 'I PE 1:3-9', tehilim: '41',
    hebcalNames: ['Vayechi'],
    resumo: 'Yaacov vive seus últimos anos no Egito. Antes de morrer, abençoa cada um de seus filhos com profecias sobre o destino de cada tribo. Yaacov é sepultado em Machpelá, e Yossef garante aos irmãos que os perdoa. Morre Yossef no Egito.',
    temas: ['Bênçãos proféticas', 'Legado', 'As doze tribos'],
  },

  // ── SHEMOT / Êxodo ──────────────────────────────────────────────────────
  {
    key: 'shemot', name: 'Shemot', hebrewName: 'שְׁמוֹת',
    traducao: 'Nomes', book: 'shemot',
    tora: 'EX 1:1–6:1', haftara: 'IS 27:6-28:13; 29:22-23', brit: 'AT 7:17-29', tehilim: '99',
    hebcalNames: ['Shemot'],
    resumo: 'Os filhos de Israel se multiplicam no Egito e um novo faraó os escraviza. Moshé nasce, é salvo das águas, cresce no palácio, foge para Midian, e Deus o chama na sarça ardente para liderar a libertação do povo.',
    temas: ['Opressão', 'Chamado profético', 'Identidade judaica'],
  },
  {
    key: 'vaera', name: 'Vaerá', hebrewName: 'וָאֵרָא',
    traducao: 'E Apareci', book: 'shemot',
    tora: 'EX 6:2–9:35', haftara: 'EZ 28:25-29:21', brit: 'RM 9:14-24', tehilim: '46',
    hebcalNames: ['Vaera', "Va'era"],
    resumo: 'Deus revela Seu nome inefável a Moshé e promete redenção. As primeiras sete pragas atingem o Egito: sangue, rãs, piolhos, animais selvagens, peste, úlceras e granizo. O coração de Faraó se endurece repetidamente.',
    temas: ['Redenção', 'Pragas', 'Poder divino'],
  },
  {
    key: 'bo', name: 'Bô', hebrewName: 'בֹּא',
    traducao: '"Vai"', book: 'shemot',
    tora: 'EX 10:1–13:16', haftara: 'JR 46:13-28', brit: 'I CO 11:20-34', tehilim: '77',
    hebcalNames: ['Bo'],
    resumo: 'As três últimas pragas: gafanhotos, trevas e a morte dos primogênitos. Os israelitas celebram o primeiro Pessach — o cordeiro pascal, a matzá e as ervas amargas. À meia-noite, Faraó expulsa o povo. Começa o Êxodo.',
    temas: ['Pessach', 'Liberdade', 'Memória'],
  },
  {
    key: 'beshalach', name: 'Beshalach', hebrewName: 'בְּשַׁלַּח',
    traducao: '"Ao Enviar"', book: 'shemot',
    tora: 'EX 13:17–17:16', haftara: 'EZ 4:4-5:31', brit: 'JO 6:22-40', tehilim: '66',
    hebcalNames: ['Beshalach'],
    resumo: 'O povo cruza o Mar Vermelho, que se abre milagrosamente. Moshé e Miriam cantam a Shirá, o cântico de louvor. No deserto, o povo reclama e Deus provê a maná do céu e água da rocha. Amalek ataca Israel.',
    temas: ['Milagres', 'Fé no deserto', 'Cântico'],
  },
  {
    key: 'yitro', name: 'Yitro', hebrewName: 'יִתְרוֹ',
    traducao: 'Jetro', book: 'shemot',
    tora: 'EX 18:1–20:26', haftara: 'IS 6:1-7:6; 9:5-6', brit: 'MT 5:17-32', tehilim: '19',
    hebcalNames: ['Yitro'],
    resumo: 'Yitro, sogro de Moshé, visita o acampamento e aconselha sobre a delegação de justiça. O povo chega ao Monte Sinai. Deus se revela com trovões e relâmpagos e proclama os Dez Mandamentos — o momento mais importante da história judaica.',
    temas: ['Os Dez Mandamentos', 'Revelação', 'Sinai'],
  },
  {
    key: 'mishpatim', name: 'Mishpatim', hebrewName: 'מִשְׁפָּטִים',
    traducao: 'Juízos', book: 'shemot',
    tora: 'EX 21:1–24:18', haftara: 'JR 34:8-22', brit: 'MT 5:38-42', tehilim: '72',
    hebcalNames: ['Mishpatim'],
    resumo: 'Logo após os Dez Mandamentos, Deus transmite dezenas de leis civis e sociais: sobre servos, danos, empréstimos, o shabbat, festas e justiça. O povo declara "Naassé veNishmá" — faremos e ouviremos. Moshé sobe ao Sinai por 40 dias.',
    temas: ['Lei judaica', 'Justiça social', 'Compromisso'],
  },
  {
    key: 'terumah', name: 'Terumah', hebrewName: 'תְּרוּמָה',
    traducao: 'Oferta', book: 'shemot',
    tora: 'EX 25:1–27:19', haftara: 'I RS 5:26-6:13', brit: 'MT 5:33-37', tehilim: '26',
    hebcalNames: ['Terumah'],
    resumo: 'Deus instrui Moshé a construir o Mishkan — o Tabernáculo portátil — para que Sua presença habite entre o povo. São detalhadas as medidas e materiais da Arca da Aliança, da Menorá, da Mesa e das cortinas do santuário.',
    temas: ['Santuário', 'Doação', 'Presença divina'],
  },
  {
    key: 'tetzaveh', name: 'Tetzaveh', hebrewName: 'תְּצַוֶּה',
    traducao: 'Ordene', book: 'shemot',
    tora: 'EX 27:20–30:10', haftara: 'EZ 43:10-27', brit: 'HB 13:10-17', tehilim: '65',
    hebcalNames: ['Tetzaveh', 'Tetzavveh'],
    resumo: 'Deus descreve as vestimentas sagradas dos sacerdotes: o éfod, o choshen (peitoral), o manto azul, a tiara e o cinto. São detalhados os procedimentos de consagração de Aharon e seus filhos e o altar de incenso.',
    temas: ['Sacerdócio', 'Vestimentas sagradas', 'Consagração'],
  },
  {
    key: 'ki-tissa', name: 'Ki Tissá', hebrewName: 'כִּי תִשָּׂא',
    traducao: 'Ao Contar', book: 'shemot',
    tora: 'EX 30:11–34:35', haftara: 'EZ 36:16-36', brit: 'I CO 8:4-13', tehilim: '75',
    hebcalNames: ['Ki Tisa', 'Ki Tissa'],
    resumo: 'O censo do meio-shekel, o óleo de unção e a pia de bronze. Enquanto Moshé demora no Sinai, o povo constrói o bezerro de ouro. Deus quer destruí-los, mas Moshé intercede. As tábuas são quebradas e depois refeitas. Os 13 atributos de misericórdia.',
    temas: ['Idolatria', 'Teshuvá', 'Misericórdia divina'],
  },
  {
    key: 'vayakhel', name: "Vaiac'hel", hebrewName: 'וַיַּקְהֵל',
    traducao: 'E Congregou', book: 'shemot',
    tora: 'EX 35:1–38:20', haftara: 'I RS 7:13-26', brit: 'HB 9:1-11', tehilim: '61',
    hebcalNames: ['Vayakhel', 'Vayakhel-Pekudei'],
    resumo: 'Moshé reúne toda a congregação e reafirma o descanso do Shabat. O povo doa generosamente materiais para a construção do Mishkan. Betsalel e Oholiav lideram a construção com sabedoria divina. O povo doa tanto que é preciso pedir que parem.',
    temas: ['Comunidade', 'Generosidade', 'Shabat'],
  },
  {
    key: 'pekudei', name: 'Pekudei', hebrewName: 'פְקוּדֵי',
    traducao: 'Conte', book: 'shemot',
    tora: 'EX 38:21–40:38', haftara: 'I RS 7:40-50', brit: 'II CO 9:6-11', tehilim: '45',
    hebcalNames: ['Pekudei', 'Vayakhel-Pekudei'],
    resumo: 'O inventário de todos os materiais usados na construção do Mishkan. Moshé erige o Tabernáculo no primeiro de Nissan. A nuvem da glória de Deus desce sobre o Mishkan, preenchendo-o. A presença divina agora habita entre o povo de Israel.',
    temas: ['Prestação de contas', 'Conclusão', 'Presença divina'],
  },

  // ── VAYICRA / Levítico ──────────────────────────────────────────────────
  {
    key: 'vayikra', name: 'Vayikrá', hebrewName: 'וַיִּקְרָא',
    traducao: 'E Chamou', book: 'vayicra',
    tora: 'LV 1:1–5:26 (6:7)', haftara: 'IS 43:21-44:23', brit: 'HB 10:1-18', tehilim: '50',
    hebcalNames: ['Vayikra'],
    resumo: 'Deus chama Moshé da Tenda do Encontro e ensina as leis dos corbanôt (oferendas): olá (elevação), minchá (farinha), shelamim (paz), chatát (pecado) e asham (culpa). Cada tipo de oferenda expressa um aspecto diferente do relacionamento com Deus.',
    temas: ['Corbanôt', 'Aproximação de Deus', 'Expiação'],
  },
  {
    key: 'tzav', name: 'Tzav', hebrewName: 'צַו',
    traducao: 'Ordene', book: 'vayicra',
    tora: 'LV 6:1(6:8)–8:36', haftara: 'JR 7:21-8:3', brit: 'HB 8:1-16', tehilim: '107',
    hebcalNames: ['Tzav'],
    resumo: 'Instruções detalhadas sobre o serviço dos sacerdotes na oferenda de cada tipo de corban. O fogo eterno deve arder continuamente no altar. Moshé consagra Aharon e seus filhos durante sete dias, inaugurando o serviço sacerdotal.',
    temas: ['Serviço sacerdotal', 'Fogo eterno', 'Inauguração'],
  },
  {
    key: 'shemini', name: 'Shemini', hebrewName: 'שְׁמִינִי',
    traducao: 'Oitavo', book: 'vayicra',
    tora: 'LV 9:1-17; 11:47', haftara: 'II SM 6:1-19', brit: 'AT 10:9-22,34,35', tehilim: '128',
    hebcalNames: ['Shemini'],
    resumo: 'No oitavo dia da inauguração, o fogo divino desce e consome as oferendas. Nadav e Avihu, filhos de Aharon, oferecem um "fogo estranho" e morrem. Aharon permanece em silêncio. São ensinadas as leis de Cashrut — animais puros e impuros.',
    temas: ['Santidade', 'Cashrut', 'Silêncio diante da tragédia'],
  },
  {
    key: 'tazria', name: 'Tazría', hebrewName: 'תַזְרִיעַ',
    traducao: 'Parturiente', book: 'vayicra',
    tora: 'LV 12:1–13:59', haftara: 'II RS 4:42-5:19', brit: 'MT 8:1-4', tehilim: '108',
    hebcalNames: ['Tazria', 'Tazria-Metzora'],
    resumo: 'Leis sobre a purificação da mulher após o parto. As leis de tzaraat — uma condição espiritual que se manifesta na pele, roupas e casas. O cohen examina e diagnostica. A tzaraat é resultado de fofoca (lashon hará).',
    temas: ['Pureza', 'Fala responsável', 'Diagnóstico espiritual'],
  },
  {
    key: 'metzora', name: 'Metzorá', hebrewName: 'מְּצֹרָע',
    traducao: 'Leproso', book: 'vayicra',
    tora: 'LV 14:1–15:33', haftara: 'II RS 7:3-20', brit: 'MT 23:16-24:2,30,31', tehilim: '120',
    hebcalNames: ['Metzora', 'Tazria-Metzora'],
    resumo: 'O processo de purificação do metzorá: isolamento, banho ritual, oferendas com duas aves, e reintegração gradual à comunidade. Tzaraat que aparece em casas. Leis sobre impurezas corporais e purificação com água.',
    temas: ['Teshuvá', 'Reintegração', 'Purificação'],
  },
  {
    key: 'acharei-mot', name: 'Acharei Mot', hebrewName: 'אַחֲרֵי מוֹת',
    traducao: 'Depois da Morte', book: 'vayicra',
    tora: 'LV 16:1–18:30', haftara: 'EZ 22:1-16', brit: 'HB 9:11-28', tehilim: '26',
    hebcalNames: ['Achrei Mot', 'Acharei Mot', 'Achrei Mot-Kedoshim'],
    resumo: 'Após a morte de Nadav e Avihu, Deus detalha o serviço de Yom Kipur — o único dia em que o Cohen Gadol entra no Santo dos Santos. O bode expiatório é enviado ao deserto. Proibição de consumir sangue e das relações proibidas.',
    temas: ['Yom Kipur', 'Expiação', 'Santidade'],
  },
  {
    key: 'kedoshim', name: 'Kedoshim', hebrewName: 'קְדֹשִׁים',
    traducao: 'Santos', book: 'vayicra',
    tora: 'LV 19:1–20:27', haftara: 'EZ 20:2-20', brit: 'MT 5:43-48', tehilim: '15',
    hebcalNames: ['Kedoshim', 'Achrei Mot-Kedoshim'],
    resumo: '"Sejam santos, pois Eu, Hashem, sou santo." Uma das parashiot mais ricas em mitzvot: respeito aos pais, Shabat, justiça nos negócios, "ame o seu próximo como a ti mesmo", não vingar, não odiar no coração, e respeitar o idoso.',
    temas: ['Santidade prática', 'Ética', 'Amor ao próximo'],
  },
  {
    key: 'emor', name: 'Emor', hebrewName: 'אֱמוֹר',
    traducao: 'Diga', book: 'vayicra',
    tora: 'LV 21:1–24:23', haftara: 'EZ 44:15-31', brit: 'LC 14:11-24', tehilim: '42',
    hebcalNames: ['Emor'],
    resumo: 'Leis especiais para os sacerdotes: pureza, casamentos e defeitos que impedem o serviço. O calendário completo das festas de Israel: Shabat, Pessach, Ômer, Shavuot, Rosh Hashaná, Yom Kipur, Sucot e Shemini Atzeret. A menorá e os pães da proposição.',
    temas: ['Festas judaicas', 'Calendário sagrado', 'Sacerdócio'],
  },
  {
    key: 'behar', name: 'Behar', hebrewName: 'בְּהַר',
    traducao: 'No Monte', book: 'vayicra',
    tora: 'LV 25:1–26:2', haftara: 'JR 32:6-27', brit: 'LC 4:16-21', tehilim: '112',
    hebcalNames: ['Behar', 'Behar-Bechukotai'],
    resumo: 'No Monte Sinai, Deus ensina as leis do ano sabático (Shemitá): a cada sete anos a terra descansa. A cada 50 anos, o Yovel (Jubileu): escravos são libertados e terras retornam aos donos originais. Leis de comércio justo e proibição de usura.',
    temas: ['Shemitá', 'Liberdade', 'Confiança em Deus'],
  },
  {
    key: 'bechukotai', name: 'Bechukotai', hebrewName: 'בְּחֻקֹּתַי',
    traducao: 'Nos Meus Estatutos', book: 'vayicra',
    tora: 'LV 26:3–27:34', haftara: 'JR 16:19-17:14', brit: 'MT 22:1-14', tehilim: '105',
    hebcalNames: ['Bechukotai', 'Behar-Bechukotai'],
    resumo: 'Se o povo seguir as leis de Deus, receberá chuvas, colheitas e paz. Se não, virão castigos progressivos: doenças, derrotas, exílio. Mas Deus nunca abandona completamente Seu povo. Leis sobre votos e avaliações para o Templo.',
    temas: ['Bênção e maldição', 'Aliança eterna', 'Teshuvá'],
  },

  // ── BAMIDBAR / Números ──────────────────────────────────────────────────
  {
    key: 'bamidbar', name: 'Bamidbar', hebrewName: 'בְּמִדְבַּר',
    traducao: 'No Deserto', book: 'bamidbar',
    tora: 'NM 1:1–4:20', haftara: 'OS 2:1-22', brit: 'I CO 12:12-20', tehilim: '122',
    hebcalNames: ['Bamidbar'],
    resumo: 'Deus ordena o censo das tribos de Israel no deserto do Sinai — 603.550 homens em idade militar. Cada tribo recebe sua posição ao redor do Mishkan. Os Levitas são separados para o serviço sagrado e contados à parte.',
    temas: ['Organização', 'As tribos', 'Serviço levítico'],
  },
  {
    key: 'nasso', name: 'Nassô', hebrewName: 'נָשֹׂא',
    traducao: 'Levante', book: 'bamidbar',
    tora: 'NM 4:21–7:89', haftara: 'JZ 13:2-25', brit: 'AT 21:17-26', tehilim: '67',
    hebcalNames: ['Naso', 'Nasso'],
    resumo: 'A parashá mais longa da Torá. Contagem dos levitas e suas funções. As leis da sotá (mulher suspeita) e do nazir (voto de abstinência). A bircat cohanim — a bênção sacerdotal tripla. As oferendas dos 12 príncipes na inauguração do altar.',
    temas: ['Bênção sacerdotal', 'Votos', 'Inauguração'],
  },
  {
    key: 'beha-alotcha', name: "Beha'alotcha", hebrewName: 'בְּהַעֲלוֹתְךָ',
    traducao: 'Ao Ascender', book: 'bamidbar',
    tora: 'NM 8:1–12:16', haftara: 'ZC 2:14-4:7', brit: 'I CO 10:6-13', tehilim: '68',
    hebcalNames: ["Beha'alotcha", "Beha'alotcha"],
    resumo: 'Aharon acende a Menorá. Os Levitas são consagrados. Pessach Sheni — uma segunda chance. As trombetas de prata e a nuvem guiam o povo. O povo reclama da comida e Deus envia codornizes. Miriam fala contra Moshé e é atingida por tzaraat.',
    temas: ['Luz', 'Segunda chance', 'Lashon hará'],
  },
  {
    key: 'shlach', name: "Sh'lach Lechá", hebrewName: 'שְׁלַח',
    traducao: 'Envie por Ti', book: 'bamidbar',
    tora: 'NM 13:1–15:41', haftara: 'JS 2:1-24', brit: 'HB 3:7-19', tehilim: '64',
    hebcalNames: ["Sh'lach", 'Shlach'],
    resumo: 'Doze espias são enviados para explorar a Terra de Israel. Dez retornam com um relatório negativo, causando pânico. Apenas Calev e Yehoshua confiam em Deus. Como castigo, a geração do deserto não entrará na terra. As leis de tzitzit.',
    temas: ['Fé vs. medo', 'Espias', 'Tzitzit'],
  },
  {
    key: 'korach', name: 'Korach', hebrewName: 'קֹרַח',
    traducao: 'Coré', book: 'bamidbar',
    tora: 'NM 16:1–18:32', haftara: 'I SM 11:14-12:22', brit: 'RM 13:1-17', tehilim: '5',
    hebcalNames: ['Korach'],
    resumo: 'Korach lidera uma rebelião contra Moshé e Aharon, questionando sua autoridade. A terra se abre e engole Korach e seus seguidores. O cajado de Aharon floresce como prova de sua escolha divina. Os dízimos e presentes dos Levitas e sacerdotes.',
    temas: ['Rebelião', 'Autoridade legítima', 'Consequências'],
  },
  {
    key: 'chukat', name: 'Chukat', hebrewName: 'חֻקַּת',
    traducao: 'Estatuto', book: 'bamidbar',
    tora: 'NM 19:1–22:1', haftara: 'JZ 11:1-33', brit: 'JO 3:10-21', tehilim: '95',
    hebcalNames: ['Chukat', 'Chukat-Balak'],
    resumo: 'A lei misteriosa da vaca vermelha para purificação. Miriam morre e falta água. Moshé bate na rocha em vez de falar com ela, e é proibido de entrar em Israel. Aharon morre no Monte Hor. Vitórias contra Sichon e Og.',
    temas: ['Mistérios da Torá', 'Humildade', 'Mortalidade'],
  },
  {
    key: 'balak', name: 'Balak', hebrewName: 'בָּלָק',
    traducao: 'Balaque', book: 'bamidbar',
    tora: 'NM 22:2–25:9', haftara: 'MQ 5:6-6:8', brit: 'I CO 1:20-31', tehilim: '79',
    hebcalNames: ['Balak', 'Chukat-Balak'],
    resumo: 'Balak, rei de Moav, contrata Bilam para amaldiçoar Israel. A jumenta de Bilam vê o anjo e fala. Cada vez que Bilam tenta amaldiçoar, saem bênçãos: "Mah tovu" — quão belas são suas tendas, ó Israel! Porém o povo peca com as moavitas.',
    temas: ['Bênção inesperada', 'Profecia', 'Mah Tovu'],
  },
  {
    key: 'pinchas', name: 'Pinchas', hebrewName: 'פִּינְחָס',
    traducao: 'Finéas', book: 'bamidbar',
    tora: 'NM 25:10–30:1', haftara: 'I RS 18:46-19:21', brit: 'JO 2:13-22', tehilim: '50',
    hebcalNames: ['Pinchas'],
    resumo: 'Pinchas recebe a aliança de paz por seu zelo. Novo censo das tribos. As filhas de Tzelafchad reclamam seu direito à herança — e vencem. Yehoshua é nomeado sucessor de Moshé. As oferendas diárias e de cada festa são detalhadas.',
    temas: ['Zelo', 'Direitos da mulher', 'Sucessão'],
  },
  {
    key: 'matot', name: 'Matot', hebrewName: 'מַּטּוֹת',
    traducao: 'Tribos', book: 'bamidbar',
    tora: 'NM 30:2–32:42', haftara: 'I RS 18:46-19:21', brit: 'FP 3:12-15', tehilim: '111',
    hebcalNames: ['Matot', 'Matot-Masei'],
    resumo: 'Leis sobre votos e juramentos, especialmente os de mulheres e a autoridade do pai ou marido. A guerra contra Midian como vingança divina. Reuven e Gad pedem para ficar na Transjordânia, e Moshé concorda com a condição de lutarem primeiro.',
    temas: ['Palavra e compromisso', 'Guerra justa', 'Responsabilidade'],
  },
  {
    key: 'masei', name: 'Massei', hebrewName: 'מַסְעֵי',
    traducao: 'Jornadas', book: 'bamidbar',
    tora: 'NM 33:1–36:13', haftara: 'JR 2:4-28, 4:1-2', brit: 'FP 3:12-16', tehilim: '49',
    hebcalNames: ['Masei', 'Matot-Masei'],
    resumo: 'Relato das 42 estações da jornada pelo deserto. As fronteiras da Terra de Israel são definidas. Seis cidades de refúgio para homicídio involuntário. As filhas de Tzelafchad se casam dentro de sua tribo para preservar a herança.',
    temas: ['Jornada', 'Fronteiras', 'Refúgio'],
  },

  // ── DEVARIM / Deuteronômio ──────────────────────────────────────────────
  {
    key: 'devarim', name: 'Devarim', hebrewName: 'דְּבָרִים',
    traducao: 'Palavras', book: 'devarim',
    tora: 'DT 1:1–3:22', haftara: 'IS 1:1-27', brit: 'I TM 1:3-17', tehilim: '137',
    hebcalNames: ['Devarim'],
    resumo: 'Moshé começa seu grande discurso de despedida. Reconta a história do deserto: os espias, as guerras, a nomeação de juízes. Repreende o povo por suas falhas mas também o encoraja. Sempre lida antes de Tishá beAv.',
    temas: ['Discurso', 'Memória histórica', 'Liderança'],
  },
  {
    key: 'vaetchanan', name: 'Vaetchanan', hebrewName: 'וָאֶתְחַנַּן',
    traducao: 'E Clamou', book: 'devarim',
    tora: 'DT 3:23–7:11', haftara: 'IS 40:1-26', brit: 'MC 12:28-34', tehilim: '90',
    hebcalNames: ['Vaetchanan'],
    resumo: 'Moshé suplica para entrar na terra, mas Deus recusa. Repete os Dez Mandamentos. Proclama o Shemá Israel — "Ouve, Israel, Hashem é nosso Deus, Hashem é Um" — a declaração mais fundamental do judaísmo. Ordena ensinar Torá aos filhos.',
    temas: ['Shemá', 'Monoteísmo', 'Educação'],
  },
  {
    key: 'eikev', name: 'Eikev', hebrewName: 'עֵקֶב',
    traducao: 'Calcanhar', book: 'devarim',
    tora: 'DT 7:12–11:25', haftara: 'IS 49:14-51:3', brit: 'RM 8:31-39', tehilim: '75',
    hebcalNames: ['Eikev'],
    resumo: 'Se o povo obedecer, Deus abençoará a terra com fartura. Moshé recorda o bezerro de ouro e as tábuas quebradas. A segunda parashá do Shemá: "Se ouvirem Meus mandamentos..." A terra de Israel é descrita como terra de leite e mel.',
    temas: ['Obediência', 'Gratidão', 'Terra de Israel'],
  },
  {
    key: 'reeh', name: "Re'eh", hebrewName: 'רְאֵה',
    traducao: 'Veja', book: 'devarim',
    tora: 'DT 11:26–16:17', haftara: 'IS 54:11-55:5', brit: 'I JO 4:1-6', tehilim: '97',
    hebcalNames: ["Re'eh"],
    resumo: '"Veja, eu ponho diante de vocês bênção e maldição." Leis sobre idolatria e o lugar que Deus escolherá (Jerusalém). Cashrut detalhada. O dízimo. Shemitá de dívidas. As três festas de peregrinação: Pessach, Shavuot e Sucot.',
    temas: ['Escolha', 'Centralidade de Jerusalém', 'Festas'],
  },
  {
    key: 'shoftim', name: 'Shoftim', hebrewName: 'שֹׁפְטִים',
    traducao: 'Juízes', book: 'devarim',
    tora: 'DT 16:18–21:9', haftara: 'IS 51:12-52:12', brit: 'AT 3:22-23', tehilim: '17',
    hebcalNames: ['Shoftim'],
    resumo: '"Justiça, justiça perseguirás!" Nomear juízes e oficiais em cada cidade. Leis do rei, do profeta, das cidades de refúgio e das testemunhas. Regras de guerra: antes de atacar, oferecer paz. Não destruir árvores frutíferas em cerco.',
    temas: ['Justiça', 'Governo', 'Ética de guerra'],
  },
  {
    key: 'ki-teitzei', name: 'Ki Teitzei', hebrewName: 'כִּי תֵצֵא',
    traducao: 'Quando Sair', book: 'devarim',
    tora: 'DT 21:10–25:19', haftara: 'IS 54:1-10', brit: 'MT 5:27-30', tehilim: '32',
    hebcalNames: ['Ki Teitzei'],
    resumo: 'Contém 74 das 613 mitzvot — mais que qualquer outra parashá. Leis sobre casamento, divórcio, primogenitura, filhos rebeldes, devolver objetos perdidos, enviar a mãe antes de pegar filhotes, não misturar espécies, e lembrar de Amalek.',
    temas: ['Mitzvot sociais', 'Compaixão', 'Lembrar Amalek'],
  },
  {
    key: 'ki-tavo', name: 'Ki Tavo', hebrewName: 'כִּי תָבוֹא',
    traducao: 'Quando Entrar', book: 'devarim',
    tora: 'DT 26:1–29:8', haftara: 'IS 60:1-22', brit: 'EF 1:3-6', tehilim: '51',
    hebcalNames: ['Ki Tavo'],
    resumo: 'Ao entrar na terra, trazer os primeiros frutos ao Templo com uma declaração de gratidão. A Tochachá — as terríveis maldições que virão se o povo abandonar a Torá. "Neste dia vocês se tornaram o povo de Deus."',
    temas: ['Primeiros frutos', 'Bênção e maldição', 'Aliança'],
  },
  {
    key: 'nitzavim', name: 'Nitzavim', hebrewName: 'נִצָּבִים',
    traducao: 'À Postos', book: 'devarim',
    tora: 'DT 29:9–30:20', haftara: 'IS 61:10-63:9', brit: 'RM 3:9-20', tehilim: '81',
    hebcalNames: ['Nitzavim', 'Nitzavim-Vayeilech'],
    resumo: 'Moshé reúne todo o povo — do líder ao lenhador — para renovar a aliança. A teshuvá é possível: "Pois esta mitzvá não está nos céus..." Deus coloca diante do povo vida e morte, bênção e maldição. "Escolha a vida!" Sempre lida antes de Rosh Hashaná.',
    temas: ['Aliança coletiva', 'Teshuvá', 'Escolha'],
  },
  {
    key: 'vayeilech', name: 'Vayeilech', hebrewName: 'וַיֵּלֶךְ',
    traducao: 'E Caminhou', book: 'devarim',
    tora: 'DT 31:1-30', haftara: 'IS 55:6-56:8', brit: 'RM 3:9-20', tehilim: '65',
    hebcalNames: ['Vayeilech', 'Nitzavim-Vayeilech'],
    resumo: 'A parashá mais curta da Torá. Moshé, aos 120 anos, se despede e transmite a liderança a Yehoshua. Ordena escrever a Torá e lê-la publicamente a cada sete anos (Hakel). Deus avisa que o povo se desviará, e ordena o cântico de testemunho.',
    temas: ['Despedida', 'Transmissão', 'Hakel'],
  },
  {
    key: 'haazinu', name: "Ha'azinu", hebrewName: 'הַאֲזִינוּ',
    traducao: 'O Cântico', book: 'devarim',
    tora: 'DT 32:1-52', haftara: 'II SM 22:1-51', brit: 'RM 3:9-20', tehilim: '71',
    hebcalNames: ["Ha'azinu"],
    resumo: 'O grande cântico poético de Moshé — uma profecia que abrange toda a história de Israel: eleição, prosperidade, esquecimento, castigo, e redenção final. "Dai ouvidos, ó céus... escute, ó terra!" Moshé recebe a ordem de subir ao Monte Nevo.',
    temas: ['Cântico profético', 'História de Israel', 'Redenção'],
  },
  {
    key: 'vezot-haberacha', name: 'Vezot Haberachá', hebrewName: 'וְזֹאת הַבְּרָכָה',
    traducao: 'Esta é a Bênção', book: 'devarim',
    tora: 'DT 33:1–34:12', haftara: 'JS 1:1-18', brit: 'RM 7:21-25', tehilim: '12',
    hebcalNames: ["V'Zot Haberakhah", 'Vezot Haberacha'],
    resumo: 'Moshé abençoa cada tribo individualmente antes de sua morte. Sobe ao Monte Nevo, vê toda a Terra Prometida, e morre aos 120 anos. "Nunca mais surgiu em Israel um profeta como Moshé." Lida em Simchat Torá, e imediatamente recomeça-se Bereshit.',
    temas: ['Bênção final', 'Morte de Moshé', 'Simchat Torá'],
  },
]

// ─── Flat ordered array of keys ────────────────────────────────────────────
export const PARASHA_ORDER: string[] = parashiot.map(p => p.key)

// ─── Known double parasha pairs ───────────────────────────────────────────
const DOUBLE_PAIRS: [string, string][] = [
  ['vayakhel', 'pekudei'],
  ['tazria', 'metzora'],
  ['acharei-mot', 'kedoshim'],
  ['behar', 'bechukotai'],
  ['chukat', 'balak'],
  ['matot', 'masei'],
  ['nitzavim', 'vayeilech'],
]

// ─── Lookup by Hebcal name ─────────────────────────────────────────────────
export function lookupParasha(hebcalName: string | null | undefined): Parasha | null {
  if (!hebcalName) return null
  const needle = hebcalName.trim().toLowerCase()

  // Check for double parasha (contains hyphen between two known names)
  for (const [keyA, keyB] of DOUBLE_PAIRS) {
    const a = parashiot.find(p => p.key === keyA)
    const b = parashiot.find(p => p.key === keyB)
    if (!a || !b) continue
    // Match against combined hebcalNames of both (e.g., "Tazria-Metzora")
    const allNames = [...a.hebcalNames, ...b.hebcalNames]
    for (const n of allNames) {
      if (n.toLowerCase() === needle && needle.includes('-') && needle.length > a.name.length) {
        // It's a double — return a merged entry
        return {
          ...a,
          key: a.key,
          name: `${a.name} + ${b.name}`,
          hebrewName: `${a.hebrewName} + ${b.hebrewName}`,
          tora: `${a.tora} / ${b.tora}`,
          haftara: b.haftara,
        }
      }
    }
  }

  // Single parasha exact match
  for (const p of parashiot) {
    for (const n of p.hebcalNames) {
      if (n.toLowerCase() === needle) return p
    }
  }
  // Fuzzy match
  for (const p of parashiot) {
    for (const n of p.hebcalNames) {
      if (n.toLowerCase().includes(needle) || needle.includes(n.toLowerCase())) return p
    }
  }
  return null
}
