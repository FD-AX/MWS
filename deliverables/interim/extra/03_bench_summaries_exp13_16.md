> Дополнительные материалы — промежуточная версия · 04.09.2026 · команда TZ Review (кейс МТС NET) · github.com/FD-AX/MWS
> Статус: завершено; recall по группам/сложности, находки, лишние, anchoring

Колонки: recall = пойманные голд-дефекты; «по группам» A пропуск, B неоднозначность, C ссылка, D противоречие, E измеримость, F шаблон; «лишних» = находки вне голда (кандидаты на разметку); anchoring = доля верифицированных цитат.

# EXP-13 — it5, 5 вариантов × 7 целей

| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |
|---|---|---|---|---|---|---|---|
| v1g | synth_v1 | **6/12** | A 1/4 B 2/3 C 2/2 D 1/2 E 0/1 | eas 2/3 med 2/6 har 2/3 | 5 | 0 | 100% |
| v1g | doc3_mart (целевой тип) | **3/16** | A 0/9 B 0/2 C 1/1 D 0/2 F 2/2 | eas 2/2 med 0/10 har 1/4 | 3 | 0 | 100% |
| v1g | doc2_source | **1/8** | A 0/3 B 0/1 C 0/1 D 0/1 E 0/1 F 1/1 | eas 1/1 med 0/5 har 0/2 | 3 | 2 | 100% |
| v1g | doc1_stream | **2/12** | A 1/6 B 0/1 C 0/1 D 0/3 F 1/1 | eas 1/1 med 1/8 har 0/3 | 4 | 0 | 100% |
| v1g | synth_v2hard | **0/8** | B 0/2 C 0/1 D 0/5 | har 0/4 exp 0/4 | 0 | 0 | 100% |
| v1g | synth_v3official | **3/13** | A 0/7 C 1/1 D 0/2 E 0/1 F 2/2 | eas 2/2 med 1/7 har 0/3 exp 0/1 | 3 | 0 | 100% |
| v1g | clean_base (шум) | — | — | 0 | noise=0 | 100% |
| v0b_gpt | synth_v1 | **10/12** | A 3/4 B 2/3 C 2/2 D 2/2 E 1/1 | eas 3/3 med 4/6 har 3/3 | 15 | 5 | 100% |
| v0b_gpt | doc3_mart (целевой тип) | **11/16** | A 6/9 B 2/2 C 1/1 D 2/2 F 0/2 | eas 0/2 med 7/10 har 4/4 | 15 | 1 | 100% |
| v0b_gpt | doc2_source | **4/8** | A 1/3 B 1/1 C 1/1 D 1/1 E 0/1 F 0/1 | eas 0/1 med 2/5 har 2/2 | 15 | 10 | 100% |
| v0b_gpt | doc1_stream | **10/12** | A 6/6 B 1/1 C 1/1 D 2/3 F 0/1 | eas 0/1 med 8/8 har 2/3 | 15 | 4 | 100% |
| v0b_gpt | synth_v2hard | **8/8** | B 2/2 C 1/1 D 5/5 | har 4/4 exp 4/4 | 15 | 2 | 100% |
| v0b_gpt | synth_v3official | **6/13** | A 2/7 C 1/1 D 2/2 E 1/1 F 0/2 | eas 0/2 med 2/7 har 3/3 exp 1/1 | 15 | 9 | 100% |
| v0b_gpt | clean_base (шум) | — | — | 15 | noise=15 | 100% |
| v2g_gpt | synth_v1 | **10/12** | A 3/4 B 2/3 C 2/2 D 2/2 E 1/1 | eas 3/3 med 4/6 har 3/3 | 16 | 1 | 81% |
| v2g_gpt | doc3_mart (целевой тип) | **13/16** | A 6/9 B 2/2 C 1/1 D 2/2 F 2/2 | eas 2/2 med 7/10 har 4/4 | 21 | 1 | 80% |
| v2g_gpt | doc2_source | **5/8** | A 1/3 B 1/1 C 1/1 D 1/1 E 0/1 F 1/1 | eas 1/1 med 2/5 har 2/2 | 25 | 20 | 86% |
| v2g_gpt | doc1_stream | **10/12** | A 6/6 B 0/1 C 1/1 D 2/3 F 1/1 | eas 1/1 med 7/8 har 2/3 | 29 | 6 | 90% |
| v2g_gpt | synth_v2hard | **8/8** | B 2/2 C 1/1 D 5/5 | har 4/4 exp 4/4 | 12 | 3 | 71% |
| v2g_gpt | synth_v3official | **9/13** | A 3/7 C 1/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 3/7 har 3/3 exp 1/1 | 13 | 4 | 77% |
| v2g_gpt | clean_base (шум) | — | — | 8 | noise=8 | 62% |
| v2e_gpt | synth_v1 | **7/12** | A 1/4 B 2/3 C 2/2 D 2/2 E 0/1 | eas 2/3 med 2/6 har 3/3 | 12 | 1 | 56% |
| v2e_gpt | doc3_mart (целевой тип) | **14/16** | A 7/9 B 2/2 C 1/1 D 2/2 F 2/2 | eas 2/2 med 8/10 har 4/4 | 16 | 3 | 88% |
| v2e_gpt | doc2_source | **5/8** | A 1/3 B 1/1 C 1/1 D 1/1 E 0/1 F 1/1 | eas 1/1 med 2/5 har 2/2 | 25 | 19 | 89% |
| v2e_gpt | doc1_stream | **9/12** | A 6/6 B 0/1 C 1/1 D 1/3 F 1/1 | eas 1/1 med 7/8 har 1/3 | 21 | 5 | 69% |
| v2e_gpt | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 12 | 3 | 83% |
| v2e_gpt | synth_v3official | **8/13** | A 3/7 C 0/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 2/7 har 3/3 exp 1/1 | 12 | 4 | 76% |
| v2e_gpt | clean_base (шум) | — | — | 9 | noise=9 | 80% |
| v2l_gpt | synth_v1 | **11/12** | A 3/4 B 3/3 C 2/2 D 2/2 E 1/1 | eas 3/3 med 5/6 har 3/3 | 16 | 1 | 79% |
| v2l_gpt | doc3_mart (целевой тип) | **10/16** | A 4/9 B 2/2 C 1/1 D 1/2 F 2/2 | eas 2/2 med 5/10 har 3/4 | 13 | 2 | 74% |
| v2l_gpt | doc2_source | **5/8** | A 2/3 B 1/1 C 1/1 D 0/1 E 0/1 F 1/1 | eas 1/1 med 3/5 har 1/2 | 28 | 19 | 89% |
| v2l_gpt | doc1_stream | **9/12** | A 6/6 B 1/1 C 0/1 D 1/3 F 1/1 | eas 1/1 med 7/8 har 1/3 | 18 | 4 | 79% |
| v2l_gpt | synth_v2hard | **8/8** | B 2/2 C 1/1 D 5/5 | har 4/4 exp 4/4 | 15 | 5 | 81% |
| v2l_gpt | synth_v3official | **7/13** | A 1/7 C 1/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 1/7 har 3/3 exp 1/1 | 12 | 4 | 79% |
| v2l_gpt | clean_base (шум) | — | — | 10 | noise=10 | 80% |

---

# EXP-14 — GPT-5.5 после фиксов

| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |
|---|---|---|---|---|---|---|---|
| v2g_gpt | synth_v1 | **7/12** | A 1/4 B 2/3 C 1/2 D 2/2 E 1/1 | eas 3/3 med 1/6 har 3/3 | 10 | 2 | 80% |
| v2g_gpt | doc3_mart (целевой тип) | **14/16** | A 8/9 B 2/2 C 1/1 D 1/2 F 2/2 | eas 2/2 med 9/10 har 3/4 | 27 | 5 | 83% |
| v2g_gpt | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 10 | 2 | 53% |
| v2g_gpt | synth_v3official | **12/13** | A 7/7 C 0/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 6/7 har 3/3 exp 1/1 | 13 | 1 | 71% |
| v2g_gpt | clean_base (шум) | — | — | 9 | noise=9 | 90% |
| v2e_gpt | synth_v1 | **10/12** | A 3/4 B 3/3 C 1/2 D 2/2 E 1/1 | eas 3/3 med 4/6 har 3/3 | 15 | 3 | 100% |
| v2e_gpt | doc3_mart (целевой тип) | **16/16** | A 9/9 B 2/2 C 1/1 D 2/2 F 2/2 | eas 2/2 med 10/10 har 4/4 | 32 | 5 | 96% |
| v2e_gpt | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 11 | 2 | 74% |
| v2e_gpt | synth_v3official | **12/13** | A 7/7 C 0/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 6/7 har 3/3 exp 1/1 | 15 | 2 | 63% |
| v2e_gpt | clean_base (шум) | — | — | 7 | noise=7 | 62% |
| v2l_gpt | synth_v1 | **7/12** | A 2/4 B 2/3 C 1/2 D 2/2 E 0/1 | eas 2/3 med 2/6 har 3/3 | 10 | 1 | 77% |
| v2l_gpt | doc3_mart (целевой тип) | **16/16** | A 9/9 B 2/2 C 1/1 D 2/2 F 2/2 | eas 2/2 med 10/10 har 4/4 | 26 | 5 | 100% |
| v2l_gpt | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 11 | 2 | 70% |
| v2l_gpt | synth_v3official | **12/13** | A 7/7 C 0/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 6/7 har 3/3 exp 1/1 | 13 | 2 | 70% |
| v2l_gpt | clean_base (шум) | — | — | 7 | noise=7 | 64% |

---

# EXP-14 повтор v2g (разброс)

| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |
|---|---|---|---|---|---|---|---|
| v2g_gpt | synth_v1 | **9/12** | A 2/4 B 2/3 C 2/2 D 2/2 E 1/1 | eas 3/3 med 3/6 har 3/3 | 16 | 4 | 81% |
| v2g_gpt | doc3_mart (целевой тип) | **16/16** | A 9/9 B 2/2 C 1/1 D 2/2 F 2/2 | eas 2/2 med 10/10 har 4/4 | 28 | 6 | 100% |
| v2g_gpt | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 13 | 3 | 67% |
| v2g_gpt | synth_v3official | **12/13** | A 6/7 C 1/1 D 2/2 E 1/1 F 2/2 | eas 2/2 med 6/7 har 3/3 exp 1/1 | 11 | 0 | 63% |
| v2g_gpt | clean_base (шум) | — | — | 9 | noise=9 | 93% |

---

# EXP-15 — gpt-oss-120b

| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |
|---|---|---|---|---|---|---|---|
| v1g | synth_v1 | **6/12** | A 1/4 B 2/3 C 2/2 D 1/2 E 0/1 | eas 2/3 med 2/6 har 2/3 | 5 | 0 | 100% |
| v1g | doc3_mart (целевой тип) | **3/16** | A 0/9 B 0/2 C 1/1 D 0/2 F 2/2 | eas 2/2 med 0/10 har 1/4 | 3 | 0 | 100% |
| v1g | synth_v2hard | **0/8** | B 0/2 C 0/1 D 0/5 | har 0/4 exp 0/4 | 0 | 0 | 100% |
| v1g | synth_v3official | **3/13** | A 0/7 C 1/1 D 0/2 E 0/1 F 2/2 | eas 2/2 med 1/7 har 0/3 exp 0/1 | 3 | 0 | 100% |
| v1g | clean_base (шум) | — | — | 0 | noise=0 | 100% |
| v2g | synth_v1 | **9/12** | A 3/4 B 2/3 C 2/2 D 2/2 E 0/1 | eas 2/3 med 4/6 har 3/3 | 14 | 2 | 71% |
| v2g | doc3_mart (целевой тип) | **12/16** | A 7/9 B 1/2 C 1/1 D 1/2 F 2/2 | eas 2/2 med 7/10 har 3/4 | 24 | 8 | 87% |
| v2g | synth_v2hard | **7/8** | B 2/2 C 1/1 D 4/5 | har 3/4 exp 4/4 | 10 | 3 | 62% |
| v2g | synth_v3official | **11/13** | A 6/7 C 1/1 D 1/2 E 1/1 F 2/2 | eas 2/2 med 7/7 har 1/3 exp 1/1 | 13 | 2 | 75% |
| v2g | clean_base (шум) | — | — | 11 | noise=11 | 58% |

---

# EXP-16 — 120b с исходом NA

| Вариант | Цель | Recall | По группам | По сложности | Находок | Лишних | Anchoring |
|---|---|---|---|---|---|---|---|
| v1g | synth_v1 | **6/12** | A 1/4 B 2/3 C 2/2 D 1/2 E 0/1 | eas 2/3 med 2/6 har 2/3 | 5 | 0 | 100% |
| v1g | doc3_mart (целевой тип) | **3/16** | A 0/9 B 0/2 C 1/1 D 0/2 F 2/2 | eas 2/2 med 0/10 har 1/4 | 3 | 0 | 100% |
| v1g | synth_v2hard | **0/8** | B 0/2 C 0/1 D 0/5 | har 0/4 exp 0/4 | 0 | 0 | 100% |
| v1g | synth_v3official | **3/13** | A 0/7 C 1/1 D 0/2 E 0/1 F 2/2 | eas 2/2 med 1/7 har 0/3 exp 0/1 | 3 | 0 | 100% |
| v1g | clean_base (шум) | — | — | 0 | noise=0 | 100% |
| v2g | synth_v1 | **9/12** | A 3/4 B 2/3 C 2/2 D 2/2 E 0/1 | eas 2/3 med 4/6 har 3/3 | 18 | 5 | 76% |
| v2g | doc3_mart (целевой тип) | **12/16** | A 7/9 B 1/2 C 1/1 D 1/2 F 2/2 | eas 2/2 med 7/10 har 3/4 | 26 | 8 | 80% |
| v2g | synth_v2hard | **6/8** | B 2/2 C 1/1 D 3/5 | har 2/4 exp 4/4 | 9 | 3 | 47% |
| v2g | synth_v3official | **10/13** | A 6/7 C 1/1 D 1/2 E 0/1 F 2/2 | eas 2/2 med 7/7 har 1/3 exp 0/1 | 20 | 9 | 83% |
| v2g | clean_base (шум) | — | — | 7 | noise=7 | 71% |