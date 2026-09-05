| Модель | Вариант | recall Σ | находок | TP лишних | FP | NA | ? | precision | шум@clean не-TP |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | v2f | 32/40 | 124 | 64 | 14 | 14 | 0 | 77% | 0 |
| gpt-oss-120b | v2g | 32/40 | 108 | 59 | 6 | 11 | 0 | 84% | 0 |

Классы мусора (FP+NA):
- gpt-oss-120b · v2f: rule-threshold 10, na-slot 8, entropy-lexical 6, placeholder-name 2, probe-noise 2
- gpt-oss-120b · v2g: rule-threshold 9, na-slot 6, placeholder-name 2
