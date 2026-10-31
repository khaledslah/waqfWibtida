import 'package:flutter/foundation.dart';

import '../models/waqf_models.dart';

const sampleSurahs = <SurahIndexEntry>[
  SurahIndexEntry(
    number: 12,
    name: 'سورة يوسف',
    status: SurahLoadStatus.inProgress,
    detail: 'الآيات ١٠٠–١١١ · ١٨ وقفًا',
  ),
  SurahIndexEntry(
    number: 18,
    name: 'سورة الكهف',
    status: SurahLoadStatus.notStarted,
    detail: 'النص غير محمّل في هذه العيّنة',
  ),
  SurahIndexEntry(
    number: 19,
    name: 'سورة مريم',
    status: SurahLoadStatus.awaitingReview,
    detail: 'بانتظار مراجعة وقوفها',
  ),
];

const sampleStops = <WaqfStop>[
  WaqfStop(
    id: 'yusuf-100-sujjadan',
    surah: 12,
    ayah: 100,
    word: 'سُجَّدًا',
    symbol: StopSymbol.jaiz,
    label: 'جائز',
    reason:
        'الوقف جائز لابتداء بيان أمر معظم مع اتفاق اللفظ، كما ذكر السجاوندي على «سجدًا».',
    inUthmaniMushaf: true,
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'جائز',
        book: 'علل الوقوف',
        page: '607',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن القطع',
        book: 'القطع والائتناف',
        page: '412',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-100-qablu',
    surah: 12,
    ayah: 100,
    word: 'قَبْلُ',
    symbol: StopSymbol.mujawwaz,
    label: 'مجوَّز',
    reason:
        'السجاوندي: الوقف على «من قبل» مجوز، لتمام الجملة لفظًا دون تمام المعنى.',
    aiSuggestion:
        'الوصل أرجح، لأن معنى الرؤيا لا يتم إلا بقوله «قد جعلها ربي حقًّا».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'مجوّز',
        book: 'علل الوقوف',
        page: '607',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: null,
        book: 'منار الهدى',
        page: '42',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-100-haqqa',
    surah: 12,
    ayah: 100,
    word: 'حَقًّا',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason:
        'ذكر السجاوندي أن الوقف على «حقًّا» تام، لتمام بيان الجملة الأولى — جعل الرؤيا حقًّا — وابتداء جملة عظمى في ذكر الإحسان والإخراج من السجن.',
    aiSuggestion:
        'يمكن اعتماد الوقف هنا لتمام قصة الرؤيا، قبل الانتقال إلى ذكر الإحسان. راجع عبارة السجاوندي قبل التثبيت.',
    opinions: [
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن القطع',
        book: 'القطع والائتناف',
        page: '149',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: 'حسن المنار',
        book: 'منار الهدى',
        page: '42',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'تام المكتفى',
        book: 'المكتفى',
        page: null,
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-100-ikhwati',
    surah: 12,
    ayah: 100,
    word: 'إِخْوَتِي',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام عند تمام ذكر نزغ الشيطان بين يوسف وإخوته، قبل الجملة الاسمية.',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'تام',
        book: 'المكتفى',
        page: '318',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-100-yashau',
    surah: 12,
    ayah: 100,
    word: 'يَشَاءُ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «لما يشاء»، ثم يُستأنف «إنه هو العليم الحكيم».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن القطع',
        book: 'القطع والائتناف',
        page: '413',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-101-ahadith',
    surah: 12,
    ayah: 101,
    word: 'الْأَحَادِيثِ',
    symbol: StopSymbol.jaiz,
    label: 'جائز',
    reason:
        'جائز لحذف حرف النداء، مع اتصال تقرير الوفاء بذكر المنة والثناء تمهيدًا للدعاء.',
    inUthmaniMushaf: true,
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'جائز',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: 'جائز',
        book: 'منار الهدى',
        page: '188',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-101-akhira',
    surah: 12,
    ayah: 101,
    word: 'وَالْآخِرَةِ',
    symbol: StopSymbol.jaiz,
    label: 'جائز',
    reason: 'الوقف جائز قبل الدعاء «توفني مسلمًا»، والوصل أوضح لاتصال الثناء بالطلب.',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'جائز',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'كاف',
        book: 'المكتفى',
        page: '319',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-102-ilayk',
    surah: 12,
    ayah: 102,
    word: 'إِلَيْكَ',
    symbol: StopSymbol.jaiz,
    label: 'جائز',
    reason: 'جائز لابتداء النفي مع واو العطف: «وما كنت لديهم».',
    inUthmaniMushaf: true,
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'جائز',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن',
        book: 'القطع والائتناف',
        page: '414',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-104-ajr',
    surah: 12,
    ayah: 104,
    word: 'أَجْرٍ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «من أجر»، ثم استئناف «إن هو إلا ذكر للعالمين».',
    inUthmaniMushaf: true,
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'تام',
        book: 'المكتفى',
        page: '319',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-108-allah',
    surah: 12,
    ayah: 108,
    word: 'اللَّهِ',
    symbol: StopSymbol.jaiz,
    label: 'جائز',
    reason:
        'جائز لاختصاص الدعوة بالله، قبل بيان أن البصيرة له ولمن اتبعه.',
    inUthmaniMushaf: true,
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'جائز',
        book: 'علل الوقوف',
        page: '608',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: 'جائز',
        book: 'منار الهدى',
        page: '189',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-108-ittabaani',
    surah: 12,
    ayah: 108,
    word: 'اتَّبَعَنِي',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «ومن اتبعني»، ثم تنزيه «وسبحان الله».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن القطع',
        book: 'القطع والائتناف',
        page: '415',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-109-qura',
    surah: 12,
    ayah: 109,
    word: 'الْقُرَى',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «من أهل القرى»، ثم استفهام «أفلم يسيروا في الأرض».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'كاف',
        book: 'المكتفى',
        page: '320',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-109-qablihim',
    surah: 12,
    ayah: 109,
    word: 'قَبْلِهِمْ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «من قبلهم»، قبل جملة «ولدار الآخرة خير».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: 'تام',
        book: 'منار الهدى',
        page: '190',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-109-ittaqaw',
    surah: 12,
    ayah: 109,
    word: 'اتَّقَوْا',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «اتقوا»، ثم «أفلا تعقلون».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: 'حسن القطع',
        book: 'القطع والائتناف',
        page: '416',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-110-kudhibu',
    surah: 12,
    ayah: 110,
    word: 'كُذِبُوا',
    symbol: StopSymbol.unsettled,
    label: 'غير محسوم',
    reason:
        'لم يذكر السجاوندي علامة على «كُذِبوا» في هذه العينة، فتُرك الحكم فارغًا حتى المراجعة.',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: null,
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: null,
        book: 'المكتفى',
        page: null,
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-110-nasr',
    surah: 12,
    ayah: 110,
    word: 'نَصْرُنَا',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason:
        'لمن قرأ «فنُنجي» بالتخفيف فالوقف على «نصرنا»، ولا يوقف على «من نشاء».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'تام',
        book: 'المكتفى',
        page: '320',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-110-nashaa',
    surah: 12,
    ayah: 110,
    word: 'نَشَاءُ',
    symbol: StopSymbol.la,
    label: 'لا تقف',
    reason:
        'على قراءة «فنُنجي» بالتخفيف لا يوقف على «من نشاء» ويوصل بما قبله. ومن قرأ «فنجّي» بالتشديد وقف عليه.',
    aiSuggestion:
        'لا تُثبَّت علامة واحدة قبل حسم وجه القراءة المعتمد. التخفيف يمنع الوقف، والتشديد يجيزه على «من نشاء».',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'لا وقف على التخفيف',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'النحاس',
        verdict: null,
        book: 'القطع والائتناف',
        page: null,
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-111-albab',
    surah: 12,
    ayah: 111,
    word: 'الْأَلْبَابِ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف تام على «لأولي الألباب»، ثم بيان أن القصص تصديق وتفصيل وهدى.',
    opinions: [
      ScholarOpinion(
        scholar: 'السجاوندي',
        verdict: 'تام',
        book: 'علل الوقوف',
        page: '609',
      ),
      ScholarOpinion(
        scholar: 'الأشموني',
        verdict: 'تام',
        book: 'منار الهدى',
        page: '191',
      ),
      ScholarOpinion(
        scholar: 'الداني',
        verdict: 'تام',
        book: 'المكتفى',
        page: '321',
      ),
    ],
  ),
  WaqfStop(
    id: 'yusuf-110-mujrimin',
    surah: 12,
    ayah: 110,
    word: 'الْمُجْرِمِينَ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف على رأس الآية — يُخفى عند تفعيل «إخفاء رؤوس الآي».',
    inUthmaniMushaf: true,
    opinions: [],
  ),
  WaqfStop(
    id: 'yusuf-111-yuminun',
    surah: 12,
    ayah: 111,
    word: 'يُؤْمِنُونَ',
    symbol: StopSymbol.tam,
    label: 'تام',
    reason: 'وقف على رأس الآية — يُخفى عند تفعيل «إخفاء رؤوس الآي».',
    inUthmaniMushaf: true,
    opinions: [],
  ),
];

const yusufAyahs = <Ayah>[
  Ayah(
    number: 100,
    words: [
      AyahWord('وَرَفَعَ'),
      AyahWord('أَبَوَيْهِ'),
      AyahWord('عَلَى'),
      AyahWord('الْعَرْشِ'),
      AyahWord('وَخَرُّوا'),
      AyahWord('لَهُ'),
      AyahWord('سُجَّدًا', 'yusuf-100-sujjadan'),
      AyahWord('وَقَالَ'),
      AyahWord('يَاأَبَتِ'),
      AyahWord('هَٰذَا'),
      AyahWord('تَأْوِيلُ'),
      AyahWord('رُؤْيَايَ'),
      AyahWord('مِن'),
      AyahWord('قَبْلُ', 'yusuf-100-qablu'),
      AyahWord('قَدْ'),
      AyahWord('جَعَلَهَا'),
      AyahWord('رَبِّي'),
      AyahWord('حَقًّا', 'yusuf-100-haqqa'),
      AyahWord('وَقَدْ'),
      AyahWord('أَحْسَنَ'),
      AyahWord('بِي'),
      AyahWord('إِذْ'),
      AyahWord('أَخْرَجَنِي'),
      AyahWord('مِنَ'),
      AyahWord('السِّجْنِ'),
      AyahWord('وَجَاءَ'),
      AyahWord('بِكُم'),
      AyahWord('مِنَ'),
      AyahWord('الْبَدْوِ'),
      AyahWord('مِن'),
      AyahWord('بَعْدِ'),
      AyahWord('أَن'),
      AyahWord('نَزَغَ'),
      AyahWord('الشَّيْطَانُ'),
      AyahWord('بَيْنِي'),
      AyahWord('وَبَيْنَ'),
      AyahWord('إِخْوَتِي', 'yusuf-100-ikhwati'),
      AyahWord('إِنَّ'),
      AyahWord('رَبِّي'),
      AyahWord('لَطِيفٌ'),
      AyahWord('لِمَا'),
      AyahWord('يَشَاءُ', 'yusuf-100-yashau'),
      AyahWord('إِنَّهُ'),
      AyahWord('هُوَ'),
      AyahWord('الْعَلِيمُ'),
      AyahWord('الْحَكِيمُ'),
    ],
  ),
  Ayah(
    number: 101,
    words: [
      AyahWord('رَبِّ'),
      AyahWord('قَدْ'),
      AyahWord('آتَيْتَنِي'),
      AyahWord('مِنَ'),
      AyahWord('الْمُلْكِ'),
      AyahWord('وَعَلَّمْتَنِي'),
      AyahWord('مِن'),
      AyahWord('تَأْوِيلِ'),
      AyahWord('الْأَحَادِيثِ', 'yusuf-101-ahadith'),
      AyahWord('فَاطِرَ'),
      AyahWord('السَّمَاوَاتِ'),
      AyahWord('وَالْأَرْضِ'),
      AyahWord('أَنْتَ'),
      AyahWord('وَلِيِّي'),
      AyahWord('فِي'),
      AyahWord('الدُّنْيَا'),
      AyahWord('وَالْآخِرَةِ', 'yusuf-101-akhira'),
      AyahWord('تَوَفَّنِي'),
      AyahWord('مُسْلِمًا'),
      AyahWord('وَأَلْحِقْنِي'),
      AyahWord('بِالصَّالِحِينَ'),
    ],
  ),
  Ayah(
    number: 102,
    words: [
      AyahWord('ذَٰلِكَ'),
      AyahWord('مِنْ'),
      AyahWord('أَنْبَاءِ'),
      AyahWord('الْغَيْبِ'),
      AyahWord('نُوحِيهِ'),
      AyahWord('إِلَيْكَ', 'yusuf-102-ilayk'),
      AyahWord('وَمَا'),
      AyahWord('كُنْتَ'),
      AyahWord('لَدَيْهِمْ'),
      AyahWord('إِذْ'),
      AyahWord('أَجْمَعُوا'),
      AyahWord('أَمْرَهُمْ'),
      AyahWord('وَهُمْ'),
      AyahWord('يَمْكُرُونَ'),
    ],
  ),
  Ayah(
    number: 103,
    words: [
      AyahWord('وَمَا'),
      AyahWord('أَكْثَرُ'),
      AyahWord('النَّاسِ'),
      AyahWord('وَلَوْ'),
      AyahWord('حَرَصْتَ'),
      AyahWord('بِمُؤْمِنِينَ'),
    ],
  ),
  Ayah(
    number: 104,
    words: [
      AyahWord('وَمَا'),
      AyahWord('تَسْأَلُهُمْ'),
      AyahWord('عَلَيْهِ'),
      AyahWord('مِنْ'),
      AyahWord('أَجْرٍ', 'yusuf-104-ajr'),
      AyahWord('إِنْ'),
      AyahWord('هُوَ'),
      AyahWord('إِلَّا'),
      AyahWord('ذِكْرٌ'),
      AyahWord('لِلْعَالَمِينَ'),
    ],
  ),
  Ayah(
    number: 105,
    words: [
      AyahWord('وَكَأَيِّنْ'),
      AyahWord('مِنْ'),
      AyahWord('آيَةٍ'),
      AyahWord('فِي'),
      AyahWord('السَّمَاوَاتِ'),
      AyahWord('وَالْأَرْضِ'),
      AyahWord('يَمُرُّونَ'),
      AyahWord('عَلَيْهَا'),
      AyahWord('وَهُمْ'),
      AyahWord('عَنْهَا'),
      AyahWord('مُعْرِضُونَ'),
    ],
  ),
  Ayah(
    number: 106,
    words: [
      AyahWord('وَمَا'),
      AyahWord('يُؤْمِنُ'),
      AyahWord('أَكْثَرُهُمْ'),
      AyahWord('بِاللَّهِ'),
      AyahWord('إِلَّا'),
      AyahWord('وَهُمْ'),
      AyahWord('مُشْرِكُونَ'),
    ],
  ),
  Ayah(
    number: 107,
    words: [
      AyahWord('أَفَأَمِنُوا'),
      AyahWord('أَنْ'),
      AyahWord('تَأْتِيَهُمْ'),
      AyahWord('غَاشِيَةٌ'),
      AyahWord('مِنْ'),
      AyahWord('عَذَابِ'),
      AyahWord('اللَّهِ'),
      AyahWord('أَوْ'),
      AyahWord('تَأْتِيَهُمُ'),
      AyahWord('السَّاعَةُ'),
      AyahWord('بَغْتَةً'),
      AyahWord('وَهُمْ'),
      AyahWord('لَا'),
      AyahWord('يَشْعُرُونَ'),
    ],
  ),
  Ayah(
    number: 108,
    words: [
      AyahWord('قُلْ'),
      AyahWord('هَٰذِهِ'),
      AyahWord('سَبِيلِي'),
      AyahWord('أَدْعُو'),
      AyahWord('إِلَى'),
      AyahWord('اللَّهِ', 'yusuf-108-allah'),
      AyahWord('عَلَىٰ'),
      AyahWord('بَصِيرَةٍ'),
      AyahWord('أَنَا'),
      AyahWord('وَمَنِ'),
      AyahWord('اتَّبَعَنِي', 'yusuf-108-ittabaani'),
      AyahWord('وَسُبْحَانَ'),
      AyahWord('اللَّهِ'),
      AyahWord('وَمَا'),
      AyahWord('أَنَا'),
      AyahWord('مِنَ'),
      AyahWord('الْمُشْرِكِينَ'),
    ],
  ),
  Ayah(
    number: 109,
    words: [
      AyahWord('وَمَا'),
      AyahWord('أَرْسَلْنَا'),
      AyahWord('مِنْ'),
      AyahWord('قَبْلِكَ'),
      AyahWord('إِلَّا'),
      AyahWord('رِجَالًا'),
      AyahWord('نُوحِي'),
      AyahWord('إِلَيْهِمْ'),
      AyahWord('مِنْ'),
      AyahWord('أَهْلِ'),
      AyahWord('الْقُرَى', 'yusuf-109-qura'),
      AyahWord('أَفَلَمْ'),
      AyahWord('يَسِيرُوا'),
      AyahWord('فِي'),
      AyahWord('الْأَرْضِ'),
      AyahWord('فَيَنْظُرُوا'),
      AyahWord('كَيْفَ'),
      AyahWord('كَانَ'),
      AyahWord('عَاقِبَةُ'),
      AyahWord('الَّذِينَ'),
      AyahWord('مِنْ'),
      AyahWord('قَبْلِهِمْ', 'yusuf-109-qablihim'),
      AyahWord('وَلَدَارُ'),
      AyahWord('الْآخِرَةِ'),
      AyahWord('خَيْرٌ'),
      AyahWord('لِلَّذِينَ'),
      AyahWord('اتَّقَوْا', 'yusuf-109-ittaqaw'),
      AyahWord('أَفَلَا'),
      AyahWord('تَعْقِلُونَ'),
    ],
  ),
  Ayah(
    number: 110,
    words: [
      AyahWord('حَتَّىٰ'),
      AyahWord('إِذَا'),
      AyahWord('اسْتَيْأَسَ'),
      AyahWord('الرُّسُلُ'),
      AyahWord('وَظَنُّوا'),
      AyahWord('أَنَّهُمْ'),
      AyahWord('قَدْ'),
      AyahWord('كُذِبُوا', 'yusuf-110-kudhibu'),
      AyahWord('جَاءَهُمْ'),
      AyahWord('نَصْرُنَا', 'yusuf-110-nasr'),
      AyahWord('فَنُجِّيَ'),
      AyahWord('مَنْ'),
      AyahWord('نَشَاءُ', 'yusuf-110-nashaa'),
      AyahWord('وَلَا'),
      AyahWord('يُرَدُّ'),
      AyahWord('بَأْسُنَا'),
      AyahWord('عَنِ'),
      AyahWord('الْقَوْمِ'),
      AyahWord('الْمُجْرِمِينَ', 'yusuf-110-mujrimin'),
    ],
  ),
  Ayah(
    number: 111,
    words: [
      AyahWord('لَقَدْ'),
      AyahWord('كَانَ'),
      AyahWord('فِي'),
      AyahWord('قَصَصِهِمْ'),
      AyahWord('عِبْرَةٌ'),
      AyahWord('لِأُولِي'),
      AyahWord('الْأَلْبَابِ', 'yusuf-111-albab'),
      AyahWord('مَا'),
      AyahWord('كَانَ'),
      AyahWord('حَدِيثًا'),
      AyahWord('يُفْتَرَىٰ'),
      AyahWord('وَلَٰكِنْ'),
      AyahWord('تَصْدِيقَ'),
      AyahWord('الَّذِي'),
      AyahWord('بَيْنَ'),
      AyahWord('يَدَيْهِ'),
      AyahWord('وَتَفْصِيلَ'),
      AyahWord('كُلِّ'),
      AyahWord('شَيْءٍ'),
      AyahWord('وَهُدًى'),
      AyahWord('وَرَحْمَةً'),
      AyahWord('لِقَوْمٍ'),
      AyahWord('يُؤْمِنُونَ', 'yusuf-111-yuminun'),
    ],
  ),
];

/// Stop ids that sit on the last word of an ayah (رأس الآية).
final Set<String> verseEndStopIds = {
  for (final ayah in yusufAyahs)
    if (ayah.words.isNotEmpty && ayah.words.last.stopId != null)
      ayah.words.last.stopId!,
};

class ReaderController extends ChangeNotifier {
  int tab = 0;
  double quranSize = 26;
  String? selectedStopId = 'yusuf-100-haqqa';
  final Set<String> sentToReview = <String>{};

  /// Hide stops on the last word of an ayah (already cued by the ayah mark).
  bool hideVerseEnd = true;

  /// Hide middle stops that already appear in the printed Uthmani mushaf.
  bool hideUthmani = true;

  WaqfStop? stopById(String id) {
    for (final stop in sampleStops) {
      if (stop.id == id) return stop;
    }
    return null;
  }

  bool isVerseEnd(WaqfStop stop) => verseEndStopIds.contains(stop.id);

  bool isStopVisible(WaqfStop stop) {
    if (hideVerseEnd && isVerseEnd(stop)) return false;
    if (hideUthmani && stop.inUthmaniMushaf) return false;
    return true;
  }

  int get visibleStopCount =>
      sampleStops.where(isStopVisible).length;

  void toggleHideVerseEnd() {
    hideVerseEnd = !hideVerseEnd;
    notifyListeners();
  }

  void toggleHideUthmani() {
    hideUthmani = !hideUthmani;
    notifyListeners();
  }

  void showAllStops() {
    if (!hideVerseEnd && !hideUthmani) return;
    hideVerseEnd = false;
    hideUthmani = false;
    notifyListeners();
  }

  void select(String id) {
    if (selectedStopId == id) return;
    selectedStopId = id;
    notifyListeners();
  }

  void markForReview(String id) {
    if (sentToReview.add(id)) notifyListeners();
  }

  bool isSent(String id) => sentToReview.contains(id);

  void setTab(int index) {
    if (tab == index) return;
    tab = index;
    notifyListeners();
  }

  void setQuranSize(double size) {
    if (quranSize == size) return;
    quranSize = size;
    notifyListeners();
  }

  List<WaqfStop> get reviewItems {
    final items = sampleStops.where((stop) {
      return stop.needsReview || sentToReview.contains(stop.id);
    }).toList();
    items.sort((a, b) {
      final byAyah = a.ayah.compareTo(b.ayah);
      if (byAyah != 0) return byAyah;
      return a.id.compareTo(b.id);
    });
    return items;
  }
}
