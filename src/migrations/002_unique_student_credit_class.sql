ALTER TABLE grades
    ADD UNIQUE KEY uq_grades_student_credit_class (student_id, credit_class_id);