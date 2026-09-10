"""
ERP query planner prompt — FALLBACK raasta.

The voice pipeline no longer uses this. It gets intent + resource +
student from a single router call and invokes ERPService.fetch()
directly (see services/groq/intent_prompt.py).

This remains only for ERPService.handle_query() — for when the caller
has just the question and does not know the resource (tests and the
like).

This prompt used to be 810 lines and spent ~4,000 tokens on every ERP
question. The reason was that it tried to produce a whole query plan —
filters, fields, limit. But the application:

    fields   -> ignores them entirely (they come from endpoint.py)
    filters  -> reads out only student_name and discards the rest
    limit    -> keeps constant

So the real output of that entire prompt was two strings. The prompt
now asks for exactly those two things.
"""


def build_erp_prompt(user_query: str) -> str:
    return f"""You are the ERP query planner for VOCIRA, a school assistant.

The caller is an authenticated guardian asking about their own children.
Reply with ONE line of JSON and nothing else. No markdown, no fences.

Shape:
{{"resource":"<name>","filters":[["student_name","=","<child name>"]]}}

Leave "filters" as [] unless the user names a specific child.
NEVER invent a name. Never add any other filter — the application adds
all authorization filters itself.

Pick exactly one "resource":

  attendance           present/absent, how many days attended
  assessment           marks, grades, results of exams already taken
  exam                 upcoming exams, when is the next exam
  schedule             class timetable: which class at what time, teacher
  class                which class / section the child is in
  course               which subjects the child studies
  program_enrollment   program and academic year
  fee                  fee amount, due date, outstanding, is fee paid
  payment              whether payment was made, how much remains
  student              child's profile: name, gender, date of birth
  guardian             the caller's own details

Examples:
"Have the fees been paid?"        -> {{"resource":"fee","filters":[]}}
"How many days was Ahmed here?"   -> {{"resource":"attendance","filters":[["student_name","=","Ahmed"]]}}
"When is the next exam?"          -> {{"resource":"exam","filters":[]}}
"What are tomorrow's classes?"    -> {{"resource":"schedule","filters":[]}}
"My children's names"             -> {{"resource":"student","filters":[]}}

User question:
{user_query}

JSON:"""
