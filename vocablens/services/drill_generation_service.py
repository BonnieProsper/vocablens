class DrillGenerationService:

    def __init__(self, llm):
        self.llm = llm

    def generate_drills(self, mistakes):

        prompt = f"""
Create exercises to fix these mistakes:

{mistakes}

Return JSON exercises.
"""

        return self.llm.generate_json(prompt)