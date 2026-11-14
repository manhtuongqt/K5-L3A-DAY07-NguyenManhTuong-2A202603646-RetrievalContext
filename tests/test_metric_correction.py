"""A model-output error must not erase evidence actually delivered to the model."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.evaluation import aggregate_agent

class ContextMetricRegression(unittest.TestCase):
    def test_valid_context_counts_even_if_final_citation_format_errors(self):
        chunk={'id':'c1','source_id':'source','source':'example://source','page':1,'text':'The documented answer is 42.'}
        case={'id':'q','answerable':True,'gold':[{'source_id':'source','page':1,'evidence':'answer is 42'}]}
        trace={'query_id':'q','status':'error','reason':'invalid_model_action','answer':'','citations':[],
               'events':[],'final_context':[chunk],'final_context_text':'[c1] The documented answer is 42.','context_ids':['c1']}
        metrics=aggregate_agent([case],[trace],[])
        self.assertEqual(metrics['context_evidence_rate']['n'],1)
        self.assertEqual(metrics['context_evidence_rate']['N'],1)
        self.assertEqual(metrics['strict_end_to_end']['n'],0)
        self.assertEqual(metrics['errors'],1)
        self.assertEqual(metrics['grounded_answer']['N'],0)

if __name__=='__main__':unittest.main()
