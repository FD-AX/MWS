import unittest

from tz_review import document
from tz_review.passes import checklist, critic, deterministic, filters
from tz_review.rubric import load_rubric
from tz_review.schema import Finding

RUBRIC = load_rubric()


def q(qid):
    return next(x for x in RUBRIC["checklist"] if x["id"] == qid)


class TestSlotApplicability(unittest.TestCase):
    def test_no_kafka_no_files_no_formulas(self):
        doc = "## Описание\nВитрина считает агрегат по абонентам. Источник — таблица TABLE_X."
        self.assertFalse(checklist.slot_applies(q("LOC-02"), doc))   # нет Kafka
        self.assertFalse(checklist.slot_applies(q("LOC-03"), doc))   # нет файловых хранилищ
        self.assertTrue(checklist.slot_applies(q("MAP-01"), doc))    # витрина/агрегат есть
        self.assertTrue(checklist.slot_applies(q("SER-01"), doc))    # без условий — всегда

    def test_kafka_and_hdfs_present(self):
        doc = "Данные идут из Kafka-топика TOPIC_A в hdfs://cluster/data/raw/"
        self.assertTrue(checklist.slot_applies(q("LOC-02"), doc))
        self.assertTrue(checklist.slot_applies(q("LOC-03"), doc))

    def test_full_reload_makes_inc03_na(self):
        self.assertFalse(checklist.slot_applies(q("INC-03"), "Обновление: полная перезапись партиции месяца."))
        self.assertTrue(checklist.slot_applies(q("INC-03"), "Инкрементальная загрузка по курсору FIELD_LOAD_ID."))

    def test_split_gives_na_statuses_without_llm_call(self):
        class NoLLM:
            def chat_json(self, *a, **k):
                raise AssertionError("не должно вызываться для NA-слотов")
        mini = {"checklist": [{"id": "LOC-02", "aspect": "x", "severity": "high", "applies_if": "kafka", "question": "?"}]}
        findings, statuses = checklist.run("Документ без брокера сообщений.", mini, NoLLM())
        self.assertEqual(statuses, {"LOC-02": "NA"})
        self.assertEqual(findings, [])


class TestPlaceholderFilter(unittest.TestCase):
    def mk(self, ask, why="", source_pass="developer_sim"):
        return Finding(category="dev_question", why=why, ask=ask, source_pass=source_pass)

    def test_drops_questions_about_real_names(self):
        bad = [self.mk("Как точно называется столбец, содержащий IMSI, в таблице TABLE_IUM_RAW_MS?"),
               self.mk("Какие названия столбцов в TABLE_DEVICE_REF хранят TAC?"),
               self.mk("", why="Без правильного имени столбца невозможно выбрать уникальных абонентов."),
               self.mk("Какие имена полей в исходных таблицах содержат LAC и CELL_ID?")]
        kept, dropped = filters.drop_placeholder_questions(bad)
        self.assertEqual(len(kept), 0)
        self.assertEqual(len(dropped), 4)
        self.assertTrue(all(f.score == 0.0 for f in dropped))

    def test_keeps_logic_questions(self):
        good = [self.mk("Что делать, если TAC отсутствует в TABLE_DEVICE_REF: NULL, UNKNOWN или отбросить запись?"),
                self.mk("По какому полю времени выбирается последний IMEI за месяц?"),
                self.mk("", why="Без правила выбора выжившей записи дедупликация недетерминирована.")]
        kept, dropped = filters.drop_placeholder_questions(good)
        self.assertEqual(len(kept), 3)

    def test_deterministic_findings_never_dropped(self):
        f = self.mk("Как называется столбец?", source_pass="doc_graph")
        kept, dropped = filters.drop_placeholder_questions([f])
        self.assertEqual(len(kept), 1)


class TestSeverityFromScore(unittest.TestCase):
    def test_mapping(self):
        self.assertEqual(critic.severity_from_score(9.0), "critical")
        self.assertEqual(critic.severity_from_score(7.0), "high")
        self.assertEqual(critic.severity_from_score(5.0), "medium")
        self.assertEqual(critic.severity_from_score(3.9), "advisory")

    def test_critic_rewrites_severity_of_llm_findings(self):
        class LLM:
            def chat_json(self, *a, **k):
                return {"scores": [{"fid": "F1", "score": 5.0}, {"fid": "F2", "score": 9.5}], "duplicates": []}
        fs = [Finding(fid="F1", category="dev_question", severity="critical", why="w", source_pass="developer_sim"),
              Finding(fid="F2", category="doc:contradiction", severity="medium", why="w", source_pass="document_level")]
        kept, _ = critic.run(fs, "doc", LLM(), threshold=4.0)
        by = {f.fid: f.severity for f in kept}
        self.assertEqual(by, {"F1": "medium", "F2": "critical"})


class TestEmptySectionRule(unittest.TestCase):
    def run_on(self, text):
        return deterministic.run(document.parse(text), RUBRIC)

    def test_one_word_answer_is_not_empty(self):
        cats = {f.category for f in self.run_on("## Регламент загрузки\nЕжемесячно\n")}
        self.assertNotIn("template:empty_section", cats)

    def test_tbd_is_empty(self):
        cats = {f.category for f in self.run_on("## Контроль качества\nTBD\n")}
        self.assertIn("template:empty_section", cats)

    def test_non_official_required_section_is_medium(self):
        fs = [f for f in self.run_on("## Источники данных\nДостаточно длинное описание источника данных здесь.\n")
              if f.category == "template:missing_section"]
        sev = {f.section: f.severity for f in fs}
        self.assertEqual(sev.get("Контроль качества"), "medium")
        self.assertEqual(sev.get("Регламент загрузки"), "medium")
        self.assertEqual(sev.get("Структура целевых таблиц"), "high")  # есть в официальном шаблоне («Структура данных»)


if __name__ == "__main__":
    unittest.main()
