"""
ERP query planner prompt — FALLBACK raasta.

Voice pipeline ab ye use NAHI karta. Wo router ke ek hi call mein
intent + resource + student le leta hai aur seedha ERPService.fetch()
bulata hai (dekhein services/groq/intent_prompt.py).

Ye sirf ERPService.handle_query() ke liye reh gaya hai — jab caller ke
paas sirf sawal ho, resource maloom na ho (tests waghera).

Pehle ye prompt 810 lines ka tha aur har ERP sawal par ~4,000 tokens
kharch karta tha. Wajah ye thi ke wo poora query plan bananay ki koshish
karta tha — filters, fields, limit. Magar application:

    fields   -> poori tarah ignore karti hai (endpoint.py se aate hain)
    filters  -> sirf student_name nikalti hai, baqi phenk deti hai
    limit    -> constant hi rakhti hai

Yaani us saare prompt ka asli nateeja do string thay. Is liye ab prompt
sirf wahi do cheezein maangta hai.
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
