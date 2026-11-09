import os,tempfile
# Isolate every test run from production and source samples.
os.environ['REVIEW_HOME']=tempfile.mkdtemp(prefix='review-tests-')

import pytest
@pytest.fixture(autouse=True)
def isolated_database():
    from backend.app.core import Session,Row
    with Session.begin() as db:db.query(Row).delete()
    yield
