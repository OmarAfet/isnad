// Every interface string in one place, in one register: white Saudi dialect (see COPY.md).
// Scripture, references, grading terms and scholars' names are data, not copy, and never pass
// through here.

export const copy = {
  brand: "إسناد",
  nav: { method: "كيف يشتغل", home: "الرئيسية" },

  hero: {
    title: "تذكر المعنى ونسيت اللفظ؟",
    subtitle: "اكتب اللي تذكره، ونطلع لك النص الصحيح بمصدره ودرجته.",
  },

  search: {
    label: "وصفك للآية أو الحديث",
    placeholder: "وش تذكر من الآية أو الحديث؟",
    hint: "اكتب بأي لغة وبأي صياغة",
    submit: "دوّر على النص",
    submitting: "ندوّر على النص",
    // Shown while every text is read; the count is the reason the wait is worth it.
    reading: "نقرأ كل النصوص",
    of: "من",
    comparing: "نقارن أقرب النصوص",
    tryLabel: "جرّب",
    tooShort: "اكتب كلمتين على الأقل",
    tooLong: "النص أطول من 300 حرف، فأخذنا أول 300.",
    // The first search after idle minutes waits while the server starts (about 8 s, measured).
    slow: "أول بحث بعد توقف ياخذ وقت أطول شوي، لأن الخدمة تشتغل من جديد.",
  },

  chain: {
    you: "وصفك",
    text: "النص",
    source: "المصدر",
    ruling: "الحكم",
    alsoIn: "ورد أيضًا في",
    otherRulings: "أحكام العلماء الآخرين",
    showSanad: "اعرض السند",
    hideSanad: "اخفِ السند",
    commentary: "تعليق صاحب الكتاب",
    translation: "الترجمة المنشورة",
    translator: (name: string) => `ترجمة ${name}`,
    translatorUnknown: "المصدر ما ذكر اسم المترجم",
    match: "تطابقه مع وصفك",
    matchHelp: "هذي نسبة تطابق النص مع وصفك، مو حكم على صحته.",
    copy: "انسخ النص",
    copied: "نسخنا النص",
    verify: "تحقق في الدرر السنية",
    alternatives: "نصوص قريبة من وصفك",
    noSource: "ما وصلنا لمصدر",
  },

  verdict: {
    confident: "لقينا النص اللي تقصده",
    tentative: "هذا أقرب نص لوصفك، بس تأكد من المصدر قبل لا تستشهد فيه.",
    unsure: "ما نقدر نجزم إنه النص اللي تقصده، فلا تستشهد فيه قبل لا تتحقق.",
    noMatch: "ما لقينا نص مطابق في المصادر المعتمدة.",
    // A hint, shown under "not found" when the description was broad.
    noMatchVague: "اكتب جزء من لفظه أو معناه عشان نلقاه.",
    searchDorar: "دوّر عليه في الدرر السنية",
    topic: "فيه أكثر من نص عن هذا. اختر اللي تقصده:",
    topicOne: "لقينا نص واحد عن وصفك:",
    backToList: "ارجع للقائمة",
    surahAll: (name: string) => `آيات سورة ${name}:`,
    surahFirst: (name: string, shown: number, total: number) =>
      `أول ${shown} آيات من سورة ${name}، وفيها ${total} آية:`,
    topicOpen: "اعرض هذا النص",
    fatwa: "سؤالك يحتاج فتوى، وإسناد ما يفتي. اسأل أهل العلم أو جهة إفتاء معتمدة.",
    unavailable: "خدمة التحقق متوقفة الحين. هذي نتائج بحث ما تأكدنا منها.",
  },

  // A ruling question: the texts on the matter, then a referral. Wording approved by Omar in the
  // preview he chose (2026-10-05); see COPY.md, "Ruling questions".
  ruling: {
    general: "النصوص الواردة في المسألة:",
    personal: "سؤالك عن حالتك أنت، والحكم فيها يحتاج عالم يسمع تفاصيلها.",
    personalTexts: "النصوص العامة الواردة في المسألة:",
    // About the search, not the sources: a judge found al-Bukhari's المعازف hadith that
    // "ما حكم الموسيقى" had not reached, and the old line read as a claim about the sources.
    none: "ما وصلنا لنصوص عن هذي المسألة.",
    noFatwa: "إسناد ما يفتي.",
    detail: "للحكم بالتفصيل:",
    fiqh: "الموسوعة الفقهية (الدرر السنية)",
    ask: "اسأل أهل العلم أو جهة إفتاء معتمدة.",
  },

  grade: {
    quran: "قرآن كريم",
    // Named, not "the scholars": the other graders of the same hadith can rule differently.
    daif: (grader?: string) =>
      `${grader ? `ضعّفه ${grader}` : "الحكم المنقول إنه ضعيف"}، فلا تنسبه للنبي ﷺ على أنه ثابت عنه.`,
    mawdu: (grader?: string) =>
      `${grader ? `حكم عليه ${grader} إنه موضوع` : "الحكم المنقول إنه موضوع"}، يعني مكذوب على النبي ﷺ. لا تنشره.`,
    unknown: "ما فيه حكم لهذا الحديث في بياناتنا.",
  },

  notFound: {
    title: "الصفحة مو موجودة",
    body: "تأكد من الرابط، أو ارجع للرئيسية ودوّر على النص من هناك.",
    home: "ارجع للرئيسية",
  },

  errors: {
    network: "ما قدرنا نوصل للخدمة. جرّب مرة ثانية.",
    rate: "طلبات كثيرة بوقت قصير. انتظر دقيقة وجرّب.",
    generic: "صار خطأ. جرّب مرة ثانية.",
  },

  footer: {
    ai: "إسناد أداة تعتمد على الذكاء الاصطناعي. تختار من نصوص موثقة وما تكتب نص من عندها.",
    rulings: "الأحكام منقولة عن العلماء بأسمائهم، وإسناد ما يفتي.",
    sources: "المصادر: القرآن الكريم بطبعة مجمع الملك فهد، والصحيحان، والسنن الأربع.",
  },
} as const;

// Language names for the translation credit line.
export const langName: Record<string, string> = {
  ar: "العربية", en: "الإنجليزية", ur: "الأردية", tr: "التركية", id: "الإندونيسية",
  bn: "البنغالية", fr: "الفرنسية", ru: "الروسية", ta: "التاميلية",
};

// Scripts written left to right, for the dir attribute on a translation.
export const ltrLangs = new Set(["en", "tr", "id", "fr", "ru", "bn", "ta"]);

// Translators' names as Arabic readers know them. These are the names the editions' own metadata
// carries; anything not listed falls back to that metadata unchanged rather than being guessed.
export const translatorAr: Record<string, string> = {
  "Muhammad Taqi Ud Din Al Hilali And Muhammad Muhsin Khan": "محمد تقي الدين الهلالي ومحمد محسن خان",
  "Muhsin Khan": "محمد محسن خان",
  "Abdul Hamid Siddiqui": "عبد الحميد صديقي",
  "King Fahd Complex": "مجمع الملك فهد",
  "Abul A Ala Maududi": "أبو الأعلى المودودي",
  "Abu Bakr Zakaria": "أبو بكر زكريا",
};
