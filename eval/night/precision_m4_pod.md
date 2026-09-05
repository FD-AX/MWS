| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | v2e | 84/98 | 145 | 18 | 37 | 6 | 0 | 70% | 26 |
| gpt-oss-120b | v2f | 89/98 | 190 | 30 | 63 | 8 | 0 | 63% | 25 |
| gpt-oss-120b | v2g | 76/98 | 118 | 22 | 15 | 5 | 0 | 83% | 18 |
| gpt-oss-120b | v2s | 84/98 | 123 | 14 | 21 | 4 | 0 | 80% | 26 |
| gpt-oss-120b | v2x | 81/98 | 119 | 20 | 12 | 6 | 0 | 85% | 20 |

Классы мусора (FP+NA):
- gpt-oss-120b · v2e: generic-whatif 28, entropy-lexical 17, na-slot 9, rule-threshold 8, base-nitpick 7
- gpt-oss-120b · v2f: entropy-lexical 46, generic-whatif 23, na-slot 10, base-nitpick 8, rule-threshold 6, probe-noise 3
- gpt-oss-120b · v2g: generic-whatif 24, na-slot 6, rule-threshold 4, base-nitpick 4
- gpt-oss-120b · v2s: generic-whatif 26, na-slot 7, rule-threshold 7, base-nitpick 7, probe-noise 4
- gpt-oss-120b · v2x: generic-whatif 21, na-slot 8, base-nitpick 5, rule-threshold 4
