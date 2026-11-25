"""Unit tests for skills/review-pr/scripts/post_drafts.py: diff parsing and comment anchoring."""
import importlib.util
import pathlib
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "skills" / "review-pr" / "scripts" / "post_drafts.py"
spec = importlib.util.spec_from_file_location("post_drafts", SCRIPT)
pd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pd)

RENAME_DELETE_ADD = """diff --git a/old/name.py b/new/name.py
similarity index 90%
rename from old/name.py
rename to new/name.py
--- a/old/name.py
+++ b/new/name.py
@@ -10,4 +10,5 @@ def f():
     a = 1
-    b = 2
+    b = 3
+    c = 4
     d = 5

diff --git a/gone.py b/gone.py
deleted file mode 100644
--- a/gone.py
+++ /dev/null
@@ -1,2 +0,0 @@
-x = 1
-y = 2
diff --git a/added.py b/added.py
new file mode 100644
--- /dev/null
+++ b/added.py
@@ -0,0 +1,2 @@
+--- not a header
+z = 1
\\ No newline at end of file
"""

SQL_COMMENTS = """diff --git a/q.sql b/q.sql
--- a/q.sql
+++ b/q.sql
@@ -1,3 +1,3 @@
--- old comment
+++ new comment
 select 1;
 select 2;
"""


class ParseDiff(unittest.TestCase):
    def setUp(self):
        self.files = pd.parse_diff(RENAME_DELETE_ADD)

    def test_deleted_files_have_no_new_side(self):
        self.assertEqual(set(self.files), {"new/name.py", "added.py"})

    def test_a_renamed_file_keeps_its_old_path(self):
        self.assertEqual(self.files["new/name.py"]["old_path"], "old/name.py")

    def test_context_lines_carry_their_old_line_and_added_lines_none(self):
        self.assertEqual(self.files["new/name.py"]["lines"], {10: 10, 11: None, 12: None, 13: 12, 14: 13})

    def test_a_new_file_is_all_added_lines(self):
        self.assertEqual(self.files["added.py"], {"old_path": "added.py", "lines": {1: None, 2: None}})

    def test_a_removed_sql_comment_inside_a_hunk_is_not_a_file_header(self):
        q = pd.parse_diff(SQL_COMMENTS)["q.sql"]
        self.assertEqual(q, {"old_path": "q.sql", "lines": {1: None, 2: 2, 3: 3}})


class SplitComments(unittest.TestCase):
    def test_only_lines_inside_a_hunk_are_anchored(self):
        files = pd.parse_diff(RENAME_DELETE_ADD)
        comments = [{"path": "new/name.py", "line": 11, "body": "on an added line"},
                    {"path": "new/name.py", "line": 40, "body": "outside every hunk"},
                    {"path": "untouched.py", "line": 1, "body": "file not in the diff"}]
        anchored, loose = pd.split_comments(comments, files)
        self.assertEqual([c["body"] for c in anchored], ["on an added line"])
        self.assertEqual([c["body"] for c in loose], ["outside every hunk", "file not in the diff"])


if __name__ == "__main__":
    unittest.main()
