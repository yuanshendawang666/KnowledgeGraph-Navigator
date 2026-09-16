import unittest
from app.services.extractor import KnowledgeExtractor


class ExtractorContractTests(unittest.TestCase):
    def test_related_to_is_retained_when_grounded(self):
        result = KnowledgeExtractor()._deduplicate_relations([
            {'source': '列表', 'target': '元组', 'relation_type': 'related_to'}
        ], [{'name': '列表'}, {'name': '元组'}])
        self.assertEqual(result[0]['relation_type'], 'related_to')

    def test_relation_deduplication_rejects_unknown_nodes(self):
        result = KnowledgeExtractor()._deduplicate_relations([
            {'source': '列表', 'target': '未知', 'relation_type': 'related_to'}
        ], [{'name': '列表'}])
        self.assertEqual(result, [])
