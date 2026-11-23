import History.AggressiveAgent as AggressiveAgent
import History.DefensiveAgent as DefensiveAgent
import History.PlayerRefCheese as CheeseAgent
import History.RandomAgent as RandomAgent
import History.AChangeOfHeart as ChangeAgent

import ContextAnalysis
import ActionEvaluation
import BehavioralEvidence
import CharacteristicUpdate

import matplotlib.pyplot as plt


Histories = {
    "Aggressive": AggressiveAgent.getHistory(),
    "Defensive": DefensiveAgent.getHistory(),
    "Cheese": CheeseAgent.getHistory(),
    "Random": RandomAgent.getHistory(),
    "Change of Heart": ChangeAgent.getHistory()
}

Iterations = 100


AllProfiles = {}
for AgentName, History in Histories.items():
    OldProfile = {
        "A": 0,
        "S": 0,
        "T": 0,

        "d_A": 0,
        "d_S": 0,
        "d_T": 0,

        "c_A": 0,
        "c_S": 0,
        "c_T": 0
    }

    ProfileGraph = []

    for i in range(Iterations):

        DecisionContext = ContextAnalysis.getDecisionContext(History[i])

        Evidence = ActionEvaluation.getEvidence(DecisionContext)

        Update = BehavioralEvidence.getUpdate(Evidence)

        NewProfile = CharacteristicUpdate.getNewProfile(
            Update,
            OldProfile
        )

        OldProfile = NewProfile

        ProfileGraph.append(NewProfile.copy())

    AllProfiles[AgentName] = ProfileGraph


Iterations_X = range(1, Iterations + 1)

Characteristics = {
    "A": "Aggression",
    "S": "Scaling",
    "T": "Teamwork",

    "d_A": "Deviation of Aggression",
    "d_S": "Deviation of Scaling",
    "d_T": "Deviation of Teamwork",

    "c_A": "Confidence of Aggression",
    "c_S": "Confidence of Scaling",
    "c_T": "Confidence of Teamwork"
}

fig, axes = plt.subplots(
    3, 3,
    figsize=(18, 12),
    gridspec_kw={
        "hspace": 0.7,
        "wspace": 0.25
    }
)

fig.canvas.manager.set_window_title("Simulation")

axes = axes.flatten()

for ax, (Characteristic, Title) in zip(
    axes,
    Characteristics.items()
):

    for AgentName, ProfileGraph in AllProfiles.items():

        Values = [
            profile[Characteristic]
            for profile in ProfileGraph
        ]

        ax.plot(
            Iterations_X,
            Values,
            label=AgentName
        )

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Value")
    ax.set_title(Title)

    ax.set_ylim(-1, 1)
    ax.grid(True)

handles, labels = axes[0].get_legend_handles_labels()

fig.legend(
    handles,
    labels,
    loc="lower center",
    ncol=5,
    fontsize=9,
    bbox_to_anchor=(0.5, 0.01)
)

plt.tight_layout(rect=[0, 0, 1, 0.93])

fig.subplots_adjust(
    top=0.95,
    bottom=0.12,
    left=0.06,
    right=0.97,
    hspace=0.6,
    wspace=0.25
)

plt.show()