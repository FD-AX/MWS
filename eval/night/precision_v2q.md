| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | v2q | 77/98 | 121 | 20 | 19 | 5 | 0 | 80% | 22 |

Классы мусора (FP+NA):
- gpt-oss-120b · v2q: generic-whatif 25, base-nitpick 8, na-slot 7, rule-threshold 4, misread 2
