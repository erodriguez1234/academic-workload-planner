"""Module membership is explicit and may be incomplete or ambiguous."""
from unittest.mock import Mock

from workload_planner.canvas_client import CanvasClientError
from workload_planner.canvas_import import convert_assignment
from workload_planner.canvas_modules import load_module_catalog

SITE="https://canvas.example.edu"
COURSE={"id":42,"name":"Course"}
def item():
    return convert_assignment({"id":7,"course_id":42,"name":"Undated","due_at":None,"submission_types":["online_upload"],"submission":{"workflow_state":"unsubmitted"}},COURSE,SITE)


def test_same_assignment_can_belong_to_multiple_modules_without_guessing_weeks():
    api=Mock()
    api.list_modules.return_value=[{"id":1,"name":"Week 3"},{"id":2,"name":"Review"}]
    api.list_module_items.return_value=[{"id":10,"type":"Assignment","content_id":7}]
    result=load_module_catalog(api,[COURSE],[item()],SITE)
    assert len(result.modules)==2 and not result.warnings
    assert all(m.assignment_ids==(item().assignment.assignment_id,) for m in result.modules)
    assert result.modules[0].key != result.modules[1].key


def test_module_access_failure_is_a_gap_and_never_removes_assignments():
    api=Mock()
    api.list_modules.return_value=[{"id":1,"name":"Week 3"},{"id":2,"name":"Review"}]
    api.list_module_items.side_effect=[CanvasClientError("access denied"),[{"type":"Assignment","content_id":7}]]
    result=load_module_catalog(api,[COURSE],[item()],SITE)
    assert len(result.modules)==1 and result.warnings


def test_quiz_module_content_id_is_not_assumed_to_be_the_assignment_id():
    api=Mock()
    api.list_modules.return_value=[{"id":1,"name":"Quiz week"}]
    api.list_module_items.return_value=[{"type":"Quiz","content_id":7}]
    result=load_module_catalog(api,[COURSE],[item()],SITE)
    assert result.modules[0].assignment_ids==()


def test_quiz_link_uses_explicit_quiz_metadata_instead_of_title_or_equal_ids():
    imported=convert_assignment({"id":7,"course_id":42,"name":"Quiz","due_at":None,"quiz_id":99,"submission_types":["online_quiz"]},COURSE,SITE)
    api=Mock()
    api.list_modules.return_value=[{"id":1,"name":"Quiz week"}]
    api.list_module_items.return_value=[{"type":"Quiz","content_id":99}]
    result=load_module_catalog(api,[COURSE],[imported],SITE)
    assert result.modules[0].assignment_ids==(imported.assignment.assignment_id,)
