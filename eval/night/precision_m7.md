| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | v2g | 78/98 | 103 | 7 | 18 | 0 | 0 | 83% | 12 |
| gpt-oss-120b | v2x | 86/98 | 125 | 20 | 19 | 0 | 0 | 85% | 18 |

Классы мусора (FP+NA):
- gpt-oss-120b · v2g: generic-whatif 28, base-nitpick 2
- gpt-oss-120b · v2x: generic-whatif 29, base-nitpick 8
