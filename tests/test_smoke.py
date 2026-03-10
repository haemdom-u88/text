import io
import time
import unittest

import app_state
from app import app
from src.graph_builder import KnowledgeGraph
from src.simple_extractor import SimpleExtractor


class DummyExtractor:
    def extract_concepts_and_edges(self, _text):
        return {"nodes": [], "edges": []}


class DummyLLM:
    def generate(self, _prompt, system_prompt=None):
        _ = system_prompt
        return "答案：测试通过\n推理链路：无"


class SmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_state.is_initialized = True
        app_state.llm_client = DummyLLM()
        app_state.extractor = DummyExtractor()
        app_state.simple_extractor = SimpleExtractor()
        app_state.kg = KnowledgeGraph()
        app_state.neo4j_store = None

    def setUp(self):
        self.client = app.test_client()

    def test_health(self):
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data.get("status"), "healthy")

    def test_upload_extract_and_graph(self):
        payload = {
            "file": (io.BytesIO("苹果公司是一家科技公司。".encode("utf-8")), "sample.txt")
        }
        resp = self.client.post("/api/upload_extract_and_graph", data=payload, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("graph", data)

    def test_extract_text(self):
        resp = self.client.post("/api/extract", json={"text": "清华大学位于北京。"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("data", data)

    def test_batch_enqueue_and_download(self):
        payload = {
            "files": (io.BytesIO("苹果公司是一家科技公司。".encode("utf-8")), "sample.txt")
        }
        resp = self.client.post("/api/batch_enqueue", data=payload, content_type="multipart/form-data")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        job_id = data.get("job_id")
        self.assertTrue(job_id)

        deadline = time.time() + 10
        job = None
        while time.time() < deadline:
            status_resp = self.client.get(f"/api/batch_status?job_id={job_id}")
            self.assertEqual(status_resp.status_code, 200)
            job_data = status_resp.get_json()
            self.assertTrue(job_data.get("success"))
            job = job_data.get("job") or {}
            if job.get("status") in {"done", "error"}:
                break
            time.sleep(0.2)

        self.assertIsNotNone(job)
        self.assertEqual(job.get("status"), "done")

        download_resp = self.client.get(f"/api/batch_download?job_id={job_id}")
        self.assertEqual(download_resp.status_code, 200)
        self.assertTrue(download_resp.data)
        download_resp.close()

    def test_export_json(self):
        resp = self.client.post("/api/export", json={"format": "json", "data": {"a": 1}})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertEqual(data.get("data"), {"a": 1})

    def test_export_pdf(self):
        resp = self.client.post("/api/export", json={"format": "pdf", "data": {"a": 1}})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/pdf", resp.content_type)
        self.assertTrue(resp.data)
        resp.close()

    def test_export_docx(self):
        resp = self.client.post("/api/export", json={"format": "docx", "data": {"a": 1}})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("application/vnd.openxmlformats-officedocument.wordprocessingml.document", resp.content_type)
        self.assertTrue(resp.data)
        resp.close()

    def test_qa_answer(self):
        resp = self.client.post("/api/qa", json={"question": "什么是知识图谱?"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data.get("success"))
        self.assertIn("result", data)

    def test_neo4j_subgraph_not_configured(self):
        resp = self.client.get("/api/neo4j/subgraph")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
