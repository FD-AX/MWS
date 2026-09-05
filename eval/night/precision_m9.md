| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | v2g | 77/98 | 105 | 17 | 11 | 0 | 0 | 90% | 10 |
| gpt-oss-120b | v2x | 83/98 | 115 | 18 | 14 | 0 | 0 | 88% | 15 |

Классы мусора (FP+NA):
- gpt-oss-120b · v2g: generic-whatif 21
- gpt-oss-120b · v2x: generic-whatif 26, base-nitpick 3
