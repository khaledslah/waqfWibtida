# Side-by-Side Comparison: Pure-LLM vs Regex (Surah 2, Ayahs 189–214)

## `s2-a189-w3` — ﴿ٱلْأَهِلَّةِ﴾ (Ayah 189, Word 3)
- **الأشموني**:
  - **Regex**: verdict=`['جائز']`, target=`عن الأهلة`
    - Comment: `وأبى الوقف عليه جماعة لأنَّ ما بعده جوابه فلا يفصل بينهما`
  - **LLM**: verdict=`['جائز', 'لا يوقف']`, target=`عن الأهلة`
    - Comment: `عن الأهلة (جائز) وأبى الوقف عليه جماعة لأنَّ ما بعده جوابه فلا يفصل بينهما.`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`عن الأهلة`
    - Comment: `للفصل بين السؤال والجواب`
  - **LLM**: verdict=`['تام']`, target=`عن الأهلة`
    - Comment: `{عن الأهلة- 189- ط} للفصل بين السؤال والجواب.`

## `s2-a189-w8` — ﴿وَٱلْحَجِّ﴾ (Ayah 189, Word 8)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`مواقيت للناس والحج`
    - Comment: `وكذلك: (مواقيت للناس والحج) [189]`
  - **LLM**: verdict=`['حسن']`, target=`مواقيت للناس والحج`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. وكذلك: (مواقيت للناس والحج) [189].`
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`والحج`
    - Comment: ``
  - **LLM**: verdict=`['كاف']`, target=`والحج`
    - Comment: `والحج (كاف).`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`للناس والحج`
    - Comment: ``
  - **LLM**: verdict=`['كاف']`, target=`للناس والحج`
    - Comment: `{للناس والحج} كاف.`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`والحج`
    - Comment: `لابتداء حكم آخر مع النفي`
  - **LLM**: verdict=`['تام']`, target=`والحج`
    - Comment: `{والحج – 189 – ط} لابتداء حكم آخر مع النفي.`
- **النحاس**:
  - **Regex**: verdict=`['تام']`, target=`قُلْ هِيَ مَوَاقِيتُ لِلنَّاسِ وَالْحَجِّ`
    - Comment: `قال أبو حاتم ﴿قُلْ هِيَ مَوَاقِيتُ لِلنَّاسِ وَالْحَجِّ﴾ تام`
  - **LLM**: verdict=`['تام']`, target=`قل هي مواقيت للناس والحج`
    - Comment: `قال أبو حاتم ﴿قُلْ هِيَ مَوَاقِيتُ لِلنَّاسِ وَالْحَجِّ﴾ تام.`

## `s2-a189-w15` — ﴿ظُهُورِهَا﴾ (Ayah 189, Word 15)
- **الأشموني**:
  - **Regex**: verdict=`['لا يوقف']`, target=`من ظهورها`
    - Comment: `من ظهورها ليس بوقف لتعلق ما بعده به عطفًا واستدراكًا`
  - **LLM**: verdict=`['لا يوقف']`, target=`من ظهورها`
    - Comment: `من ظهورها ليس بوقف لتعلق ما بعده به عطفًا واستدراكًا.`

## `s2-a189-w19` — ﴿ٱتَّقَىٰ﴾ (Ayah 189, Word 19)
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`من اتقى`
    - Comment: `ومثله من أبوابها`
  - **LLM**: verdict=`['كاف']`, target=`من اتقى`
    - Comment: `من اتقى (كاف) ومثله من أبوابها.`
- **السجاوندي**:
  - **Regex**: verdict=`['جائز']`, target=`من اتقى`
    - Comment: `لعطف الجملتين المختلفتين`
  - **LLM**: verdict=`['جائز']`, target=`من اتقى`
    - Comment: `{من اتقى- 189- ج} لعطف الجملتين المختلفتين.`

## `s2-a189-w23` — ﴿أَبْوَٰبِهَا﴾ (Ayah 189, Word 23)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`من أبوابها`
    - Comment: `وكذلك: (من أبوابها)، و(لعلكم تفلحون)`
  - **LLM**: verdict=`['حسن']`, target=`من أبوابها`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. وكذلك: (مواقيت للناس والحج) [189] وكذلك: (من أبوابها).`
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`من أبوابها`
    - Comment: `ومثله من أبوابها`
  - **LLM**: verdict=`['كاف']`, target=`من أبوابها`
    - Comment: `من اتقى (كاف) ومثله من أبوابها.`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`من أبوابها`
    - Comment: `ومثله {من أبوابها}`
  - **LLM**: verdict=`['كاف']`, target=`من أبوابها`
    - Comment: `{للناس والحج} كاف، ومثله {من أبوابها}.`
- **السجاوندي**:
  - **Regex**: verdict=`['حسن']`, target=`أبوابها`
    - Comment: `لعطف المتفقتين`
  - **LLM**: verdict=`['حسن']`, target=`أبوابها`
    - Comment: `{أبوابها- 189- ص} لعطف المتفقتين.`

## `s2-a189-w27` — ﴿تُفْلِحُونَ﴾ (Ayah 189, Word 27)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`لعلكم تفلحون`
    - Comment: `وكذلك: (من أبوابها)، و(لعلكم تفلحون)`
  - **LLM**: verdict=`['حسن']`, target=`لعلكم تفلحون`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. وكذلك: (مواقيت للناس والحج) [189] وكذلك: (من أبوابها)، و(لعلكم تفلحون).`
- **الأشموني**:
  - **Regex**: verdict=`['تام']`, target=`تفلحون`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`تفلحون`
    - Comment: `تفلحون (تام).`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`لعلكم تفلحون`
    - Comment: `وكذلك {لعلكم تفلحون}  كاف`
  - **LLM**: verdict=`['كاف']`, target=`لعلكم تفلحون`
    - Comment: `وكذلك {لعلكم تفلحون} كاف.`
- **النحاس**:
  - **Regex**: verdict=`['حسن']`, target=`لَعَلَّكُمْ تُفْلِحُونَ`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾`
  - **LLM**: verdict=`['حسن']`, target=`لعلكم تفلحون`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن.`

## `s2-a190-w8` — ﴿تَعْتَدُوٓا۟﴾ (Ayah 190, Word 8)
- **الأشموني**:
  - **Regex**: verdict=`['صالح']`, target=`ولا تعتدوا`
    - Comment: `لأن قوله إن الله جواب للنهي قبله فله به بعض تعلق`
  - **LLM**: verdict=`['صالح']`, target=`ولا تعتدوا`
    - Comment: `ولا تعتدوا (صالح) لأن قوله إن الله جواب للنهي قبله فله به بعض تعلق.`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`ولا تعتدوا`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`ولا تعتدوا`
    - Comment: `{ولا تعتدوا- 190 – ط}.`

## `s2-a190-w13` — ﴿ٱلْمُعْتَدِينَ﴾ (Ayah 190, Word 13)
- **الأشموني**:
  - **Regex**: verdict=`['تام']`, target=`المعتدين`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`المعتدين`
    - Comment: `المعتدين (تام).`
- **النحاس**:
  - **Regex**: verdict=`['حسن']`, target=`إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾`
  - **LLM**: verdict=`['حسن']`, target=`إن الله لا يحب المعتدين`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾.`

## `s2-a191-w7` — ﴿أَخْرَجُوكُمْ﴾ (Ayah 191, Word 7)
- **الأشموني**:
  - **Regex**: verdict=`['حسن']`, target=`من حيث أخرجوكم`
    - Comment: `ومثله من القتل`
  - **LLM**: verdict=`['حسن']`, target=`من حيث أخرجوكم`
    - Comment: `من حيث أخرجوكم (حسن) ومثله من القتل.`

## `s2-a191-w11` — ﴿ٱلْقَتْلِ﴾ (Ayah 191, Word 11)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`والفتنة أشد من القتل`
    - Comment: `(والفتنة أشد من القتل)`
  - **LLM**: verdict=`['حسن']`, target=`والفتنة أشد من القتل`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. وكذلك: (مواقيت للناس والحج) [189] وكذلك: (من أبوابها)، و(لعلكم تفلحون)، (والفتنة أشد من القتل).`
- **الأشموني**:
  - **Regex**: verdict=`['حسن']`, target=`من القتل`
    - Comment: `ومثله من القتل`
  - **LLM**: verdict=`['حسن']`, target=`من القتل`
    - Comment: `من حيث أخرجوكم (حسن) ومثله من القتل.`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`أشد من القتل`
    - Comment: `ومثله {أشد من القتل}`
  - **LLM**: verdict=`['كاف']`, target=`أشد من القتل`
    - Comment: `وكذلك {لعلكم تفلحون} كاف. ومثله {أشد من القتل}.`
- **السجاوندي**:
  - **Regex**: verdict=`['جائز']`, target=`من القتل`
    - Comment: `للعارض بين الجملتين المتفقتين، ومن قرأ: {ولا تقاتلوهم} بالألف فوقفه أجوز، لتبدل الحكم، فإن الأول أمر بالقتل مطلقًا حيث كان، والثاني نهي عن ابتداء القتال عند المسجد الحرام`
  - **LLM**: verdict=`['جائز']`, target=`من القتل`
    - Comment: `{من القتل – 191 – ج} للعارض بين الجملتين المتفقتين، ومن قرأ: {ولا تقاتلوهم} بالألف فوقفه أجوز، لتبدل الحكم، فإن الأول أمر بالقتل مطلقًا حيث كان، والثاني نهي عن ابتداء القتال عند المسجد الحرام.`
- **النحاس**:
  - **Regex**: verdict=`['حسن']`, target=`الفتنة أشد من القتل`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾`
  - **LLM**: verdict=`['حسن']`, target=`الفتنة أشد من القتل`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾.`

## `s2-a191-w19` — ﴿فِيهِ﴾ (Ayah 191, Word 19)
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`حتى يقاتلوكم فيه`
    - Comment: `للابتداء بالشرط مع الفاء`
  - **LLM**: verdict=`['كاف']`, target=`حتى يقاتلوكم فيه`
    - Comment: `حتى يقاتلوكم فيه (كاف) للابتداء بالشرط مع الفاء.`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`حتى يقاتلوكم فيه`
    - Comment: `ومثله {حتى يقاتلوكم فيه}`
  - **LLM**: verdict=`['كاف']`, target=`حتى يقاتلوكم فيه`
    - Comment: `وكذلك {لعلكم تفلحون} كاف. ومثله {أشد من القتل} ومثله {حتى يقاتلوكم فيه}.`
- **السجاوندي**:
  - **Regex**: verdict=`['جائز']`, target=`فيه`
    - Comment: `للابتداء بالشرط مع الفاء`
  - **LLM**: verdict=`['جائز']`, target=`فيه`
    - Comment: `{فيه- 191 – ج} للابتداء بالشرط مع الفاء.`

## `s2-a191-w22` — ﴿فَٱقْتُلُوهُمْ﴾ (Ayah 191, Word 22)
- **الأشموني**:
  - **Regex**: verdict=`['جائز']`, target=`فاقتلوهم`
    - Comment: `لأنَّ قوله كذلك جزاء الكافرين منقطع في اللفظ متصل المعنى`
  - **LLM**: verdict=`['جائز']`, target=`فاقتلوهم`
    - Comment: `فاقتلوهم (جائز) لأنَّ قوله كذلك جزاء الكافرين منقطع في اللفظ متصل المعنى.`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`فاقتلوهم`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`فاقتلوهم`
    - Comment: `{فاقتلوهم- 191- ط}.`

## `s2-a191-w25` — ﴿ٱلْكَـٰفِرِينَ﴾ (Ayah 191, Word 25)
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`الكافرين`
    - Comment: ``
  - **LLM**: verdict=`['كاف']`, target=`الكافرين`
    - Comment: `الكافرين (كاف).`
- **النحاس**:
  - **Regex**: verdict=`['حسن']`, target=`كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾`
  - **LLM**: verdict=`['حسن']`, target=`كذلك جزاء الكافرين`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾.`

## `s2-a192-w6` — ﴿رَّحِيمٌۭ﴾ (Ayah 192, Word 6)
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`رحيم`
    - Comment: `أكفى منه`
  - **LLM**: verdict=`['كاف']`, target=`رحيم`
    - Comment: `الكافرين (كاف)، رحيم (أكفى) منه.`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`غفور رحيم`
    - Comment: `ومثله {غفور رحيم}`
  - **LLM**: verdict=`['كاف']`, target=`غفور رحيم`
    - Comment: `وكذلك {لعلكم تفلحون} كاف. ومثله {أشد من القتل} ومثله {حتى يقاتلوكم فيه}، ومثله {غفور رحيم}.`
- **النحاس**:
  - **Regex**: verdict=`['حسن']`, target=`فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾`
  - **LLM**: verdict=`['حسن']`, target=`فإن انتهوا فإن الله غفور رحيم`
    - Comment: `﴿لَعَلَّكُمْ تُفْلِحُونَ﴾ وقف حسن وكذا ﴿إِنَّ اللَّهَ لَا يُحِبُّ الْمُعْتَدِينَ﴾ وكذا ﴿الفتنة أشد من القتل﴾ وكذا ﴿كَذَٰلِكَ جَزَاءُ الْكَافِرِينَ﴾ وكذا ﴿فَإِنِ انتَهَوْا فَإِنَّ اللَّهَ غَفُورٌ رَّحِيمٌ﴾.`

## `s2-a193-w3` — ﴿لَا﴾ (Ayah 193, Word 3)
- **ابن الأنباري**: Regex had `['لا يوقف', 'جائز']` (`لا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a193-w5` — ﴿فِتْنَةٌۭ﴾ (Ayah 193, Word 5)
- **الأشموني**:
  - **Regex**: verdict=`['لا يوقف']`, target=`فتنة`
    - Comment: `فتنة ليس بوقف لأن ما بعده معطوف على ما قبله`
  - **LLM**: verdict=`['لا يوقف']`, target=`فتنة`
    - Comment: `فتنة ليس بوقف لأن ما بعده معطوف على ما قبله.`

## `s2-a193-w8` — ﴿لِلَّهِ﴾ (Ayah 193, Word 8)
- **الأشموني**:
  - **Regex**: verdict=`['حسن']`, target=`الدين لله`
    - Comment: ``
  - **LLM**: verdict=`['حسن']`, target=`الدين لله`
    - Comment: `الدين لله (حسن).`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`الدين لله`
    - Comment: `لتبدل الحكم والحال`
  - **LLM**: verdict=`['تام']`, target=`الدين لله`
    - Comment: `{الدين لله- 193- ط} لتبدل الحكم والحال.`

## `s2-a193-w15` — ﴿ٱلظَّـٰلِمِينَ﴾ (Ayah 193, Word 15)
- **الأشموني**:
  - **Regex**: verdict=`['تام']`, target=`الظالمين`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`الظالمين`
    - Comment: `الظالمين (تام).`
- **الداني**:
  - **Regex**: verdict=`['تام']`, target=`على الظالمين`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`على الظالمين`
    - Comment: `{على الظالمين} تام.`
- **النحاس**:
  - **Regex**: verdict=`['تام']`, target=`فَلَا عُدْوَانَ إِلَّا عَلَى الظَّالِمِينَ`
    - Comment: `والتمام ﴿فَلَا عُدْوَانَ إِلَّا عَلَى الظَّالِمِينَ﴾ ثم الوقف بعده عند أبي حاتم ﴿وَالْحُرُمَاتُ قِصَاصٌ﴾`
  - **LLM**: verdict=`['تام']`, target=`فلا عدوان إلا على الظالمين`
    - Comment: `والتمام ﴿فَلَا عُدْوَانَ إِلَّا عَلَى الظَّالِمِينَ﴾.`

## `s2-a194-w6` — ﴿قِصَاصٌۭ﴾ (Ayah 194, Word 6)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`والحرمات قصاص`
    - Comment: `وكذلك (والحرمات قصاص) [194]`
  - **LLM**: verdict=`['حسن']`, target=`والحرمات قصاص`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. وكذلك: (مواقيت للناس والحج) [189] وكذلك: (من أبوابها)، و(لعلكم تفلحون)، (والفتنة أشد من القتل). وكذلك (والحرمات قصاص) [194].`
- **الأشموني**:
  - **Regex**: verdict=`['كاف']`, target=`قصاص`
    - Comment: ``
  - **LLM**: verdict=`['كاف']`, target=`قصاص`
    - Comment: `قصاص (كاف).`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`والحرمات قصاص`
    - Comment: ``
  - **LLM**: verdict=`['كاف']`, target=`والحرمات قصاص`
    - Comment: `{والحرمات قصاص} كاف.`
- **السجاوندي**:
  - **Regex**: verdict=`['تام']`, target=`قصاص`
    - Comment: `لأن الاعتداء خارج عن أصل الموجب وفرعه`
  - **LLM**: verdict=`['تام']`, target=`قصاص`
    - Comment: `{قصاص- 194- ط} لأن الاعتداء خارج عن أصل الموجب وفرعه.`
- **النحاس**: **LLM recovered** `['كاف']` (`والحرمات قصاص`) — missed by Regex!
  - Comment: `ثم الوقف بعده عند أبي حاتم ﴿وَالْحُرُمَاتُ قِصَاصٌ﴾.`

## `s2-a194-w9` — ﴿عَلَيْكُمْ﴾ (Ayah 194, Word 9)
- **الأشموني**: Regex had `['حسن']` (`عليكم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a194-w15` — ﴿عَلَيْكُمْ﴾ (Ayah 194, Word 15)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`بمثل ما اعتدى عليكم`
    - Comment: `وكذلك (بمثل ما اعتدى عليكم)`
  - **LLM**: verdict=`['حسن']`, target=`بمثل ما اعتدى عليكم`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. ... وكذلك (والحرمات قصاص) [194]. وكذلك (بمثل ما اعتدى عليكم).`
- **الأشموني**: **LLM recovered** `['حسن']` (`عليكم`) — missed by Regex!
  - Comment: `عليكم (حسن).`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`بمثل ما اعتدى عليكم`
    - Comment: `ومثله {بمثل ما اعتدى عليكم}`
  - **LLM**: verdict=`['كاف']`, target=`بمثل ما اعتدى عليكم`
    - Comment: `{والحرمات قصاص} كاف. ومثله {بمثل ما اعتدى عليكم}.`
- **السجاوندي**:
  - **Regex**: verdict=`['حسن']`, target=`ما اعتدى عليكم`
    - Comment: `لعطف الجملتين المتفقتين`
  - **LLM**: verdict=`['حسن']`, target=`ما اعتدى عليكم`
    - Comment: `{ما اعتدى عليكم- 194- ص} لعطف الجملتين المتفقتين.`

## `s2-a194-w17` — ﴿ٱللَّهَ﴾ (Ayah 194, Word 17)
- **الأشموني**:
  - **Regex**: verdict=`['حسن']`, target=`واتقوا الله`
    - Comment: ``
  - **LLM**: verdict=`['حسن']`, target=`واتقوا الله`
    - Comment: `عليكم (حسن)، واتقوا الله (أحسن).`

## `s2-a194-w22` — ﴿ٱلْمُتَّقِينَ﴾ (Ayah 194, Word 22)
- **ابن الأنباري**:
  - **Regex**: verdict=`['حسن']`, target=`واعلموا أن الله مع المتقين`
    - Comment: `وكذلك (واعلموا أن الله مع المتقين)`
  - **LLM**: verdict=`['حسن']`, target=`واعلموا أن الله مع المتقين`
    - Comment: `والوقف على (من الهدى والفرقان) حسن. ... وكذلك (والحرمات قصاص) [194]. وكذلك (بمثل ما اعتدى عليكم). وكذلك (واعلموا أن الله مع المتقين).`
- **الأشموني**:
  - **Regex**: verdict=`['تام']`, target=`المتقين`
    - Comment: ``
  - **LLM**: verdict=`['تام']`, target=`المتقين`
    - Comment: `المتقين (تام).`
- **الداني**:
  - **Regex**: verdict=`['كاف']`, target=`مع المتقين`
    - Comment: `ومثله {مع المتقين}`
  - **LLM**: verdict=`['كاف']`, target=`مع المتقين`
    - Comment: `{والحرمات قصاص} كاف. ومثله {بمثل ما اعتدى عليكم}. ومثله {مع المتقين}.`
- **النحاس**:
  - **Regex**: verdict=`['كاف']`, target=`وَاعْلَمُوا أَنَّ اللَّهَ مَعَ الْمُتَّقِينَ`
    - Comment: `﴿وَاعْلَمُوا أَنَّ اللَّهَ مَعَ الْمُتَّقِينَ﴾ قطع كاف، وكذا ﴿وَأَحْسِنُوا﴾ ، قال سفيان: أي وأحسنوا بالله الظن، قال يعقوب`
  - **LLM**: verdict=`['كاف']`, target=`واعلموا أن الله مع المتقين`
    - Comment: `﴿وَاعْلَمُوا أَنَّ اللَّهَ مَعَ الْمُتَّقِينَ﴾ قطع كاف.`

## `s2-a195-w9` — ﴿ٱلتَّهْلُكَةِ﴾ (Ayah 195, Word 9)
- **الأشموني**: Regex had `['حسن']` (`إلى التهلكة`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`التهلكة`), LLM omitted (false/non-stop in regex or missed).

## `s2-a195-w10` — ﴿وَأَحْسِنُوٓا۟﴾ (Ayah 195, Word 10)
- **الأشموني**: Regex had `['جائز']` (`وأحسنوا`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`وأحسنوا`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`وَأَحْسِنُوا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a195-w14` — ﴿ٱلْمُحْسِنِينَ﴾ (Ayah 195, Word 14)
- **ابن الأنباري**: Regex had `['حسن']` (`إن الله يحب المحسنين`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`المحسنين`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`يحب المحسنين`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w2` — ﴿ٱلْحَجَّ﴾ (Ayah 196, Word 2)
- **ابن الأنباري**: Regex had `['لا يوقف']` (`الحج`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن', 'لا يوقف']` (`وأتموا الحج`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w4` — ﴿لِلَّهِ﴾ (Ayah 196, Word 4)
- **الأشموني**: Regex had `['كاف']` (`لله`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`والعمرة لله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`والعمرة لله`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['جائز']` (`وَأَتِمُّوا الْحَجَّ وَالْعُمْرَةَ لِلَّهِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w10` — ﴿ٱلْهَدْىِ﴾ (Ayah 196, Word 10)
- **ابن الأنباري**: Regex had `['حسن']` (`فما استيسر من الهدي`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`من الهدي`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`فَإِنْ أُحْصِرْتُمْ فَمَا اسْتَيْسَرَ مِنَ الْهَدْيِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w17` — ﴿مَحِلَّهُۥ﴾ (Ayah 196, Word 17)
- **الداني**: Regex had `['كاف']` (`الهدي محله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`محله`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`حَتَّىٰ يَبْلُغَ الْهَدْيُ مَحِلَّهُ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w33` — ﴿نُسُكٍۢ﴾ (Ayah 196, Word 33)
- **السجاوندي**: Regex had `['جائز']` (`أو نسك`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`أَوْ نُسُكٍ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w35` — ﴿أَمِنتُمْ﴾ (Ayah 196, Word 35)
- **السجاوندي**: Regex had `['حسن']` (`أمنتم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w40` — ﴿ٱلْحَجِّ﴾ (Ayah 196, Word 40)
- **الأشموني**: Regex had `['لا يوقف']` (`إلى الحج`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w44` — ﴿ٱلْهَدْىِ﴾ (Ayah 196, Word 44)
- **الأشموني**: Regex had `['كاف']` (`من الهدى`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`من الهدي`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`من الهدي`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w55` — ﴿رَجَعْتُمْ﴾ (Ayah 196, Word 55)
- **الأشموني**: Regex had `['حسن']` (`إذا رجعتم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`رجعتم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w58` — ﴿كَامِلَةٌۭ﴾ (Ayah 196, Word 58)
- **الأشموني**: Regex had `['حسن']` (`كاملة`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`كاملة`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w66` — ﴿ٱلْحَرَامِ﴾ (Ayah 196, Word 66)
- **ابن الأنباري**: Regex had `['حسن']` (`ذلك لمن لم يكن أهله حاضري المسجد الحرام`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن']` (`المسجد الحرام`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف', 'تام']` (`حاضري المسجد الحرام`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`الحرام`), LLM omitted (false/non-stop in regex or missed).

## `s2-a196-w73` — ﴿ٱلْعِقَابِ﴾ (Ayah 196, Word 73)
- **ابن الأنباري**: Regex had `['تام']` (`أن الله شديد العقاب`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`العقاب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`شديد العقاب`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`شَدِيدُ الْعِقَابِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w1` — ﴿ٱلْحَجُّ﴾ (Ayah 197, Word 1)
- **ابن الأنباري**: Regex had `['لا يوقف']` (`الحج`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w3` — ﴿مَّعْلُومَـٰتٌۭ﴾ (Ayah 197, Word 3)
- **الأشموني**: Regex had `['كاف']` (`معلومات`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`معلومات`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['صالح', 'حسن', 'تام']` (`الْحَجُّ أَشْهُرٌ مَّعْلُومَاتٌ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w11` — ﴿فُسُوقَ﴾ (Ayah 197, Word 11)
- **ابن الأنباري**: Regex had `['جائز']` (`فلا رفث ولا فسوق`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`فلا رفث ولا فسوق`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w15` — ﴿ٱلْحَجِّ﴾ (Ayah 197, Word 15)
- **ابن الأنباري**: Regex had `['جائز']` (`في الحج`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف', 'تام']` (`ولا جدال في الحج`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`ولا جدال في الحج`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`في الحج`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w19` — ﴿خَيْرٍۢ﴾ (Ayah 197, Word 19)
- **الأشموني**: Regex had `['لا يوقف']` (`من خير`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w21` — ﴿ٱللَّهُ﴾ (Ayah 197, Word 21)
- **ابن الأنباري**: Regex had `['تام']` (`يعلمه الله`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`يعلمه الله`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`يعلمه الله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`يعلمه الله`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`وَمَا تَفْعَلُوا مِنْ خَيْرٍ يَعْلَمْهُ اللَّهُ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w22` — ﴿وَتَزَوَّدُوا۟﴾ (Ayah 197, Word 22)
- **النحاس**: Regex had `['كاف']` (`وَتَزَوَّدُوا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w26` — ﴿ٱلتَّقْوَىٰ﴾ (Ayah 197, Word 26)
- **ابن الأنباري**: Regex had `['حسن']` (`فإن خير الزاد التقوى`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`التقوى`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`التقوى`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`التقوى`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w27` — ﴿وَٱتَّقُونِ﴾ (Ayah 197, Word 27)
- **النحاس**: Regex had `['جائز']` (`واتقون`), LLM omitted (false/non-stop in regex or missed).

## `s2-a197-w29` — ﴿ٱلْأَلْبَـٰبِ﴾ (Ayah 197, Word 29)
- **ابن الأنباري**: Regex had `['تام']` (`واتقون يا أولي الألباب`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`والألباب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`يا أولي الألباب`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف', 'تام']` (`فَإِنَّ خَيْرَ الزَّادِ التَّقْوَىٰ وَاتَّقُونِ يَا أُولِي الْأَلْبَابِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a198-w3` — ﴿جُنَاحٌ﴾ (Ayah 198, Word 3)
- **الأشموني**: Regex had `['لا يوقف']` (`ليس عليكم جناح`), LLM omitted (false/non-stop in regex or missed).

## `s2-a198-w8` — ﴿رَّبِّكُمْ﴾ (Ayah 198, Word 8)
- **ابن الأنباري**: Regex had `['حسن']` (`أن تبتغوا فضلا من ربكم`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن']` (`من ربكم`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`فضلاً من ربكم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`من ربكم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a198-w17` — ﴿ٱلْحَرَامِ﴾ (Ayah 198, Word 17)
- **الأشموني**: Regex had `['حسن']` (`الحرام`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['حسن']` (`الحرام`), LLM omitted (false/non-stop in regex or missed).

## `s2-a198-w20` — ﴿هَدَىٰكُمْ﴾ (Ayah 198, Word 20)
- **الأشموني**: Regex had `['لا يوقف']` (`كما هداكم`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`كما هداكم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`هداكم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a198-w26` — ﴿ٱلضَّآلِّينَ﴾ (Ayah 198, Word 26)
- **الأشموني**: Regex had `['كاف']` (`الضالين`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`لمن الضالين`), LLM omitted (false/non-stop in regex or missed).

## `s2-a199-w6` — ﴿ٱلنَّاسُ﴾ (Ayah 199, Word 6)
- **الأشموني**: Regex had `['جائز']` (`أفاض الناس`), LLM omitted (false/non-stop in regex or missed).

## `s2-a199-w8` — ﴿ٱللَّهَ﴾ (Ayah 199, Word 8)
- **الأشموني**: Regex had `['كاف']` (`واستغفروا الله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`واستغفروا الله`), LLM omitted (false/non-stop in regex or missed).

## `s2-a199-w12` — ﴿رَّحِيمٌۭ﴾ (Ayah 199, Word 12)
- **الأشموني**: Regex had `['تام']` (`رحيم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a200-w10` — ﴿ذِكْرًۭا﴾ (Ayah 200, Word 10)
- **ابن الأنباري**: Regex had `['جائز']` (`أو أشد ذكرا`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`ذكرًا`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`أو أشد ذكرًا`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`ذكرًا`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`أَوْ أَشَدَّ ذِكْرًا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a200-w24` — ﴿خَلَـٰقٍۢ﴾ (Ayah 200, Word 24)
- **الأشموني**: Regex had `['كاف']` (`من خلاق`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`من خلاق`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`مِنْ خَلَاقٍ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a201-w14` — ﴿ٱلنَّارِ﴾ (Ayah 201, Word 14)
- **الأشموني**: Regex had `['كاف']` (`عذاب النار`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`وَقِنَا عَذَابَ النَّارِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a202-w5` — ﴿كَسَبُوا۟﴾ (Ayah 202, Word 5)
- **الداني**: Regex had `['كاف', 'تام']` (`مما كسبوا`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`مما كسبوا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a202-w8` — ﴿ٱلْحِسَابِ﴾ (Ayah 202, Word 8)
- **ابن الأنباري**: Regex had `['تام']` (`والله سريع الحساب`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`الحساب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`الحساب`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`وَاللَّهُ سَرِيعُ الْحِسَابِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a203-w5` — ﴿مَّعْدُودَٰتٍۢ﴾ (Ayah 203, Word 5)
- **ابن الأنباري**: Regex had `['حسن']` (`في أيام معدودات`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`معدودات`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`معدودات`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`معدودات`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['جائز']` (`فِي أَيَّامٍ مَّعْدُودَاتٍ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a203-w12` — ﴿عَلَيْهِ﴾ (Ayah 203, Word 12)
- **الأشموني**: Regex had `['جائز']` (`فلا إثم عليه`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`عليه`), LLM omitted (false/non-stop in regex or missed).

## `s2-a203-w17` — ﴿عَلَيْهِ﴾ (Ayah 203, Word 17)
- **السجاوندي**: Regex had `['لا يوقف']` (`عليه`), LLM omitted (false/non-stop in regex or missed).

## `s2-a203-w19` — ﴿ٱتَّقَىٰ﴾ (Ayah 203, Word 19)
- **ابن الأنباري**: Regex had `['جائز']` (`لمن اتقى`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن', 'كاف']` (`لمن اتقى`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف', 'تام']` (`لمن اتقى`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`اتقى`), LLM omitted (false/non-stop in regex or missed).

## `s2-a203-w25` — ﴿تُحْشَرُونَ﴾ (Ayah 203, Word 25)
- **الأشموني**: Regex had `['تام']` (`تحشرون`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`إليه تحشرون`), LLM omitted (false/non-stop in regex or missed).

## `s2-a204-w14` — ﴿قَلْبِهِۦ﴾ (Ayah 204, Word 14)
- **الأشموني**: Regex had `['لا يوقف']` (`على ما في قلبه`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['لا يوقف']` (`قلبه`), LLM omitted (false/non-stop in regex or missed).

## `s2-a204-w17` — ﴿ٱلْخِصَامِ﴾ (Ayah 204, Word 17)
- **الأشموني**: Regex had `['كاف', 'لا يوقف']` (`الخصام`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`ألد الخصام`), LLM omitted (false/non-stop in regex or missed).

## `s2-a205-w7` — ﴿فِيهَا﴾ (Ayah 205, Word 7)
- **ابن الأنباري**: Regex had `['لا يوقف', 'جائز', 'تام']` (`ليفسد فيها`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`ليفسد فيها`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['جائز']` (`لِيُفْسِدَ فِيهَا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a205-w8` — ﴿وَيُهْلِكَ﴾ (Ayah 205, Word 8)
- **ابن الأنباري**: Regex had `['لا يوقف']` (`ويهلك`), LLM omitted (false/non-stop in regex or missed).

## `s2-a205-w10` — ﴿وَٱلنَّسْلَ﴾ (Ayah 205, Word 10)
- **الأشموني**: Regex had `['كاف']` (`والنسل`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`الحرث والنسل`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`والنسل`), LLM omitted (false/non-stop in regex or missed).

## `s2-a205-w14` — ﴿ٱلْفَسَادَ﴾ (Ayah 205, Word 14)
- **ابن الأنباري**: Regex had `['جائز']` (`الفساد`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`الفساد`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`الفساد`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['جائز']` (`وَيُهْلِكَ الْحَرْثَ وَالنَّسْلَ وَاللَّهُ لَا يُحِبُّ الْفَسَادَ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a206-w8` — ﴿بِٱلْإِثْمِ﴾ (Ayah 206, Word 8)
- **الأشموني**: Regex had `['جائز']` (`بالإثم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a206-w10` — ﴿جَهَنَّمُ﴾ (Ayah 206, Word 10)
- **ابن الأنباري**: Regex had `['حسن']` (`فحسبه جهنم`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`جهنم`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`فحسبه جهنم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`جهنم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a206-w12` — ﴿ٱلْمِهَادُ﴾ (Ayah 206, Word 12)
- **الأشموني**: Regex had `['تام']` (`المهاد`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`المهاد`), LLM omitted (false/non-stop in regex or missed).

## `s2-a207-w8` — ﴿ٱللَّهِ﴾ (Ayah 207, Word 8)
- **ابن الأنباري**: Regex had `['تام']` (`ابتغاء مرضات الله`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`مرضاة الله`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`ابتغاء مرضات الله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`مرضات الله`), LLM omitted (false/non-stop in regex or missed).

## `s2-a207-w11` — ﴿بِٱلْعِبَادِ﴾ (Ayah 207, Word 11)
- **ابن الأنباري**: Regex had `['جائز']` (`العباد`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`بالعباد`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`بالعباد`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`والله رؤوف بالعباد`), LLM omitted (false/non-stop in regex or missed).

## `s2-a208-w7` — ﴿كَآفَّةًۭ﴾ (Ayah 208, Word 7)
- **الأشموني**: Regex had `['جائز']` (`كافة`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['حسن']` (`كافة`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`يَا أَيُّهَا الَّذِينَ آمَنُوا ادْخُلُوا فِي السِّلْمِ كَافَّةً`), LLM omitted (false/non-stop in regex or missed).

## `s2-a208-w11` — ﴿ٱلشَّيْطَـٰنِ﴾ (Ayah 208, Word 11)
- **الأشموني**: Regex had `['كاف']` (`الشيطان`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`الشيطان`), LLM omitted (false/non-stop in regex or missed).

## `s2-a208-w15` — ﴿مُّبِينٌۭ﴾ (Ayah 208, Word 15)
- **الأشموني**: Regex had `['كاف']` (`مبين`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`وَلَا تَتَّبِعُوا خُطُوَاتِ الشَّيْطَانِ إِنَّهُ لَكُمْ عَدُوٌّ مُّبِينٌ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a209-w12` — ﴿حَكِيمٌ﴾ (Ayah 209, Word 12)
- **الأشموني**: Regex had `['تام']` (`حكيم`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`فَاعْلَمُوا أَنَّ اللَّهَ عَزِيزٌ حَكِيمٌ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a210-w10` — ﴿ٱلْغَمَامِ﴾ (Ayah 210, Word 10)
- **الأشموني**: Regex had `['كاف', 'لا يوقف']` (`من الغمام`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`هل ينظرون إلا أن يأتيهم الله في ظلل من الغمام`), LLM omitted (false/non-stop in regex or missed).

## `s2-a210-w11` — ﴿وَٱلْمَلَـٰٓئِكَةُ﴾ (Ayah 210, Word 11)
- **ابن الأنباري**: Regex had `['جائز', 'حسن']` (`الملائكة`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن', 'لا يوقف']` (`والملائكة`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`وَالْمَلَائِكَةِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a210-w13` — ﴿ٱلْأَمْرُ﴾ (Ayah 210, Word 13)
- **السجاوندي**: Regex had `['تام']` (`وقضي الأمر`), LLM omitted (false/non-stop in regex or missed).

## `s2-a210-w17` — ﴿ٱلْأُمُورُ﴾ (Ayah 210, Word 17)
- **ابن الأنباري**: Regex had `['تام']` (`الأمور`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`الأمور`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`الأمور`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`وَإِلَى اللَّهِ تُرْجَعُ الْأُمُورُ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a211-w8` — ﴿بَيِّنَةٍۢ﴾ (Ayah 211, Word 8)
- **ابن الأنباري**: Regex had `['حسن']` (`من آية بينة`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن']` (`بينة`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`من آية بينة`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`بينة`), LLM omitted (false/non-stop in regex or missed).

## `s2-a211-w20` — ﴿ٱلْعِقَابِ﴾ (Ayah 211, Word 20)
- **الأشموني**: Regex had `['تام']` (`العقاب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`شديد العقاب`), LLM omitted (false/non-stop in regex or missed).

## `s2-a212-w9` — ﴿ءَامَنُوا۟﴾ (Ayah 212, Word 9)
- **ابن الأنباري**: Regex had `['حسن']` (`ويسخرون من الذين آمنوا`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن']` (`آمنوا`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`من الذين آمنوا`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['لازم']` (`من الذين آمنوا`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['حسن']` (`وَيَسْخَرُونَ مِنَ الَّذِينَ آمَنُوا`), LLM omitted (false/non-stop in regex or missed).

## `s2-a212-w14` — ﴿ٱلْقِيَـٰمَةِ﴾ (Ayah 212, Word 14)
- **ابن الأنباري**: Regex had `['جائز']` (`القيامة`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن']` (`يوم القيامة`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`يوم القيامة`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`يوم القيامة`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`وَالَّذِينَ اتَّقَوْا فَوْقَهُمْ يَوْمَ الْقِيَامَةِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a212-w20` — ﴿حِسَابٍۢ﴾ (Ayah 212, Word 20)
- **الأشموني**: Regex had `['تام']` (`بغير حساب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`بغير حساب`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام', 'صالح']` (`وَاللَّهُ يَرْزُقُ مَن يَشَاءُ بِغَيْرِ حِسَابٍ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w4` — ﴿وَٰحِدَةًۭ﴾ (Ayah 213, Word 4)
- **الأشموني**: Regex had `['لا يوقف']` (`واحدة`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w9` — ﴿وَمُنذِرِينَ﴾ (Ayah 213, Word 9)
- **الأشموني**: Regex had `['جائز']` (`منذرين`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['حسن']` (`ومنذرين`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w19` — ﴿فِيهِ﴾ (Ayah 213, Word 19)
- **الأشموني**: Regex had `['حسن']` (`فيما اختلفوا فيه`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`فيما اختلفوا فيه`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`فيما اختلفوا فيه`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w30` — ﴿ٱلْبَيِّنَـٰتُ﴾ (Ayah 213, Word 30)
- **النحاس**: Regex had `['كاف']` (`من بعد ما جاءتهم البينات`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w32` — ﴿بَيْنَهُمْ﴾ (Ayah 213, Word 32)
- **الأشموني**: Regex had `['حسن']` (`بغيًا بينهم`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف', 'تام']` (`بغيًا بينهم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['جائز']` (`بينهم`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`وَمَا اخْتَلَفَ فِيهِ إِلَّا الَّذِينَ أُوتُوهُ مِن بَعْدِ مَا جَاءَتْهُمُ الْبَيِّنَاتُ بَغْيًا بَيْنَهُمْ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w42` — ﴿بِإِذْنِهِۦ﴾ (Ayah 213, Word 42)
- **ابن الأنباري**: Regex had `['حسن']` (`من الحق بإذنه`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['كاف']` (`بإذنه`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`من الحق بإذنه`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`بإذنه`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['صالح']` (`بَغْيًا بَيْنَهُمْ فَهَدَى اللَّهُ الَّذِينَ آمَنُوا لِمَا اخْتَلَفُوا فِيهِ مِنَ الْحَقِّ بِإِذْنِهِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a213-w49` — ﴿مُّسْتَقِيمٍ﴾ (Ayah 213, Word 49)
- **الأشموني**: Regex had `['تام']` (`مستقيم`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`مستقيم`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`وَاللَّهُ يَهْدِي مَن يَشَاءُ إِلَىٰ صِرَاطٍ مُّسْتَقِيمٍ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a214-w12` — ﴿قَبْلِكُم﴾ (Ayah 214, Word 12)
- **الأشموني**: Regex had `['حسن']` (`من قبلكم`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`من قبلكم`), LLM omitted (false/non-stop in regex or missed).

## `s2-a214-w25` — ﴿ٱللَّهِ﴾ (Ayah 214, Word 25)
- **ابن الأنباري**: Regex had `['حسن']` (`متى نصر الله`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['حسن', 'كاف']` (`متى نصر الله`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['كاف']` (`متى نصر الله`), LLM omitted (false/non-stop in regex or missed).
- **السجاوندي**: Regex had `['تام']` (`متى نصر الله`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['كاف']` (`مَتَىٰ نَصْرُ اللَّهِ`), LLM omitted (false/non-stop in regex or missed).

## `s2-a214-w30` — ﴿قَرِيبٌۭ﴾ (Ayah 214, Word 30)
- **ابن الأنباري**: Regex had `['تام']` (`إن نصر الله قريب`), LLM omitted (false/non-stop in regex or missed).
- **الأشموني**: Regex had `['تام']` (`قريب`), LLM omitted (false/non-stop in regex or missed).
- **الداني**: Regex had `['تام']` (`قريبٌ`), LLM omitted (false/non-stop in regex or missed).
- **النحاس**: Regex had `['تام']` (`أَلَا إِنَّ نَصْرَ اللَّهِ قَرِيبٌ`), LLM omitted (false/non-stop in regex or missed).
