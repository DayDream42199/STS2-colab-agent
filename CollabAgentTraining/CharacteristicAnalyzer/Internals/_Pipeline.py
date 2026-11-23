from . import ContextAnalysis
from . import ActionEvaluation
from . import BehavioralEvidence
from . import CharacteristicUpdate

OUTPUT_KEYS = ("A", "S", "T", "c_A", "c_S", "c_T")


def run(history, oldProfile):
    decisionContext = ContextAnalysis.getDecisionContext(history)
    evidence = ActionEvaluation.getEvidence(decisionContext)
    update = BehavioralEvidence.getUpdate(evidence)
    return CharacteristicUpdate.getNewProfile(update, oldProfile)


def output(profile):
    return {k: profile[k] for k in OUTPUT_KEYS}
