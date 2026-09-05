"""
09_EMBEDDINGS (part 1) — turn a raw contextual field + its surrounding
structured facts into a rich sentence BEFORE embedding it (design doc
Section 6: never embed the raw remark alone).
"""


def build_internship_context(student_name: str, institution_name: str, company: str,
                              duration: str, year: int, performance_remark: str) -> str:
    return (
        f"{student_name}, a {institution_name} student, completed a {duration} "
        f"internship at {company} in {year}. Performance notes: {performance_remark}"
    )


def build_faculty_context(faculty_name: str, institution_name: str, research_interests: str) -> str:
    return (
        f"{faculty_name} is on faculty at {institution_name}, "
        f"with research interests in {research_interests}."
    )


def build_institution_context(institution_name: str, extra_remark: str) -> str:
    return f"{institution_name}: {extra_remark}"


if __name__ == "__main__":
    print(build_internship_context(
        "Rahul Sharma", "IIT Delhi", "Google", "6-month", 2025,
        "Excellent performance, demonstrated strong ML and analytical skills",
    ))
