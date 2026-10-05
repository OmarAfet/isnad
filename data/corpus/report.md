# Isnad corpus report

- records: **40389** — 6236 ayahs, 34153 hadiths

## Split coverage (hadith only)

| rule | count | share |
|---|---|---|
| `quote` | 12898 | 37.8% |
| `prophet_speech` | 8538 | 25.0% |
| `after_chain` | 8316 | 24.3% |
| `an_prophet` | 2273 | 6.7% |
| `unsplit` | 2128 | 6.2% |

**Split succeeded on 32025/34153 = 93.8%.**

## Empty source text: 0 (0.00%)

Hadiths whose upstream edition carries no text. `02_normalize.py` excludes them from the corpus, so this count reads 0 after a clean build; 379 were dropped at build time (muslim 203, nasai 86, tirmidhi 74, bukhari 9, ibnmajah 5, abudawud 2).



## Unsplit: 2128 (6.2%)

No sanad boundary was found, so `matn` still holds the whole report including the chain. These stay searchable; the cost is that transmitter names remain in the embedded text.

- `bukhari:94` — حَدَّثَنَا عَبْدَةُ، قَالَ حَدَّثَنَا عَبْدُ الصَّمَدِ، قَالَ حَدَّثَنَا عَبْدُ اللَّهِ بْنُ الْمُثَنَّى، قَالَ حَدَّثَنَا ثُمَامَةُ بْنُ عَبْدِ اللَّ

- `bukhari:95` — حَدَّثَنَا عَبْدَةُ بْنُ عَبْدِ اللَّهِ، حَدَّثَنَا عَبْدُ الصَّمَدِ، قَالَ حَدَّثَنَا عَبْدُ اللَّهِ بْنُ الْمُثَنَّى، قَالَ حَدَّثَنَا ثُمَامَةُ بْن

- `bukhari:127` — حَدَّثَنَا عُبَيْدُ اللَّهِ بْنُ مُوسَى عَنْ مَعْرُوفِ بْنِ خَرَّبُوذٍ عَنْ أَبِي الطُّفَيْلِ عَنْ عَلِيٍّ بِذَلِكَ

## Short matn (< 25 normalized chars): 1288

Checked by hand, not a defect list: many genuine matns are this short ("اللهم علمه الكتاب"). Listed so a bad split cannot hide among them.
- `bukhari:75` rule=`quote` matn='اللَّهُمَّ عَلِّمْهُ الْكِتَابَ'
- `bukhari:102` rule=`quote` matn='ثَلاَثَةً لَمْ يَبْلُغُوا الْحِنْثَ'
- `bukhari:165` rule=`prophet_speech` matn='وَيْلٌ لِلأَعْقَابِ مِنَ النَّارِ'
- `bukhari:181` rule=`quote` matn='الْمُصَلَّى أَمَامَكَ'
- `bukhari:238` rule=`prophet_speech` matn='نَحْنُ الآخِرُونَ السَّابِقُونَ'

## Grading provenance

| basis | count | meaning |
|---|---|---|
| `cited` | 19169 | explicit ruling by a named muhaddith |
| `inherent` | 14940 | sound by inclusion in a Sahih collection |
| `quran` | 6236 | Quranic text, no grading applies |
| `none` | 44 | **no ruling in the data — Isnad must not state a grade** |

Hadiths with no usable ruling: **44** (0.1% of hadith).

tirmidhi=35, nasai=7, ibnmajah=2

### Named graders present (8 distinct)

- Zubair Ali Zai: 19033
- Al-Albani: 18925
- Shuaib Al Arnaut: 6409
- Abu Ghuddah: 5609
- Muhammad Muhyi Al-Din Abdul Hamid: 5169
- Muhammad Fouad Abd al-Baqi: 4309
- Ahmad Muhammad Shakir: 3667
- Bashar Awad Maarouf: 2384

### Distinct grade values (1658)

Sahih (32113), Daif (9838), Hasan (5588), Hasan Sahih (3391), Sahih - Agreed Upon (2002), Isnaad Hasan (1940), Isnaad Sahih (1916), Sahih Muslim (1574), Sahih Isnaad (842), Sahih Lighairihi (783), Daif Isnaad (626), Sahih Bukhari (589), Very Daif (466), Sahih - Bukhari And Muslim (383)

## Length profile

- ayah: min 2, median 52, p95 154, max 676 normalized chars
- hadith matn: min 12, median 114, p95 470, max 6920 normalized chars
