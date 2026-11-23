"""Editable original interest statements for a thesis prototype, NOT a validated test.

Keep the R/I/A/S/E/C block order and five items per block stable: stored answers
and synthetic data use that exact ordering. Changing scoring/order needs an
explicit data migration and review; do not silently reinterpret old responses.
"""

from validation import RIASEC_TYPES, score_riasec


TYPE_NAMES = {"R": "Realistic", "I": "Investigative", "A": "Artistic",
              "S": "Social", "E": "Enterprising", "C": "Conventional"}
LIKERT_LABELS = {1: "Strongly Dislike", 2: "Dislike", 3: "Neutral", 4: "Like", 5: "Strongly Like"}
QUESTION_GROUPS = {
    "R": (
        "Build a small object using tools and materials.",
        "Repair a simple mechanical device.",
        "Set up equipment for a hands-on activity.",
        "Work outdoors on a practical project.",
        "Assemble parts by following a technical drawing.",
    ),
    "I": (
        "Investigate why a scientific experiment produced a result.",
        "Solve a challenging mathematics or logic problem.",
        "Compare evidence to answer a research question.",
        "Explore how living things or natural systems work.",
        "Analyze data to identify patterns.",
    ),
    "A": (
        "Create an original drawing or visual design.",
        "Write a story, poem, or creative script.",
        "Make music or take part in a performance.",
        "Develop an imaginative design for a space or object.",
        "Express an idea through photography or video.",
    ),
    "S": (
        "Help a classmate understand a difficult lesson.",
        "Listen to someone who needs support.",
        "Volunteer to help people in the community.",
        "Guide a group through a learning activity.",
        "Help someone learn a new skill patiently.",
    ),
    "E": (
        "Present an idea to persuade a group.",
        "Lead a team toward a shared project goal.",
        "Plan how to promote a school activity.",
        "Negotiate responsibilities or resources for a project.",
        "Develop a plan for a small business or initiative.",
    ),
    "C": (
        "Organize records so information is easy to find.",
        "Check a table of numbers for mistakes.",
        "Follow a detailed procedure to complete a task.",
        "Maintain an accurate schedule or task checklist.",
        "Sort and label information using a consistent system.",
    ),
}
QUESTIONS = tuple(
    {"id": f"{kind}{item}", "type": kind, "text": text}
    for kind in RIASEC_TYPES for item, text in enumerate(QUESTION_GROUPS[kind], start=1)
)
ASSESSMENT_LIMITATION = (
    "This editable interest questionnaire is a prototype, not a validated psychological assessment. "
    "Your answers describe interests and should support discussion with a guidance counselor."
)


def holland_summary(answers: list[int]) -> dict:
    """Derive scores and preserve ties instead of inventing a primary/secondary order."""
    scores = score_riasec(answers)
    levels = sorted(set(scores.values()), reverse=True)
    dominant = [kind for kind in RIASEC_TYPES if scores[kind] == levels[0]]
    # A tied highest score has no unique primary/secondary ordering.
    secondary = [kind for kind in RIASEC_TYPES if scores[kind] == levels[1]] if len(dominant) == 1 else []
    return {"scores": scores, "dominant": dominant, "secondary": secondary}
