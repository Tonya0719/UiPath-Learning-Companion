from __future__ import annotations

from typing import Literal, Optional, Union
from pydantic import BaseModel, Field, model_validator
Status = Literal['ANSWERED', 'INSUFFICIENT_EVIDENCE', 'NEED_MORE_INFORMATION', 'OUT_OF_SCOPE']

class Evidence(BaseModel):
    source_id: str
    source_label: str = ''
    text: str = ''
    source_pages: list[int] = Field(default_factory=list)
    url: Optional[str] = None
    product: Optional[str] = None
    version: Optional[str] = None
    checked_on: Optional[str] = None

class LearningAnswer(BaseModel):
    status: Status
    answer: str = ''
    key_concept: str = ''
    exercise_connection: Optional[str] = None
    common_misunderstanding: Optional[str] = None
    need_more_information: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    @model_validator(mode='after')
    def check_answer(self):
        if self.status == 'ANSWERED' and not self.answer.strip():
            raise ValueError('Answered response requires answer text')
        return self

class NextStepAnswer(BaseModel):
    status: Status
    where_you_are: str = ''
    next_actions: list[str] = Field(default_factory=list, max_length=3)
    activity_or_expression: list[str] = Field(default_factory=list)
    expected_result: str = ''
    common_mistake: Optional[str] = None
    verification: str = ''
    need_more_information: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    @model_validator(mode='after')
    def check_answer(self):
        if self.status == 'ANSWERED' and (not self.next_actions or not self.verification):
            raise ValueError('Next step requires actions and verification')
        return self

class DebugCause(BaseModel):
    cause: str
    check: str
    fix: str
    rationale: str = ''
    confidence: Optional[float] = Field(default=None, ge=0, le=1)

class DebugAnswer(BaseModel):
    status: Status
    diagnosis_type: Literal['EXERCISE_STEP', 'WORKFLOW_LOGIC', 'ENVIRONMENT_SETUP', 'PLATFORM_VERSION', 'INSUFFICIENT_INFORMATION'] = 'INSUFFICIENT_INFORMATION'
    possible_causes: list[DebugCause] = Field(default_factory=list, max_length=3)
    verification: str = ''
    need_more_information: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    @model_validator(mode='after')
    def check_answer(self):
        if self.status == 'ANSWERED' and (not self.possible_causes or not self.verification):
            raise ValueError('Diagnosis requires causes and verification')
        return self

class PracticeQuestion(BaseModel):
    status: Literal['GENERATED', 'UNSUPPORTED_TOPIC', 'NEEDS_REVIEW']
    reason: str = ''
    question_id: str = ''
    question: str = ''
    options: dict[str, str] = Field(default_factory=dict)
    knowledge_point: str = ''
    question_type: str = ''
    difficulty: str = ''
    course_evidence_ids: list[str] = Field(default_factory=list)
    reference_question_ids: list[str] = Field(default_factory=list)
    correct_answer: str = ''
    answer_rationale: str = ''
    review_status: Literal['NEEDS_HUMAN_REVIEW', 'APPROVED', 'NOT_APPLICABLE'] = 'NEEDS_HUMAN_REVIEW'
    @model_validator(mode='after')
    def check_question(self):
        if self.status != 'GENERATED':
            self.review_status = 'NOT_APPLICABLE'
        if self.status == 'GENERATED':
            if set(self.options) != set('ABCD') or self.correct_answer not in self.options:
                raise ValueError('A-D options and valid answer required')
            if len({x.strip().casefold() for x in self.options.values()}) != 4 or any(not x.strip() for x in self.options.values()):
                raise ValueError('Options must be nonempty and distinct')
            if not self.question.strip() or not self.answer_rationale.strip():
                raise ValueError('Question and rationale required')
        return self

class QuestionExplanation(BaseModel):
    status: Union[Status, Literal['NEEDS_REVIEW']] = 'ANSWERED'
    reason: str = ''
    correct_answer: str = ''
    knowledge_point: str = ''
    why_correct: str = ''
    why_others_wrong: dict[str, str] = Field(default_factory=dict)
    learning_takeaway: str = ''
    student_misunderstanding: Optional[str] = None
    evidence: list[Evidence] = Field(default_factory=list)
