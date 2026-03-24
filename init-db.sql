-- Create a read-only role for executing user queries
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'querymind_readonly') THEN
        CREATE ROLE querymind_readonly LOGIN PASSWORD 'R3adOnly!_Dev#2024';
    END IF;
END
$$;

-- Grant read-only access to public schema
GRANT CONNECT ON DATABASE querymind TO querymind_readonly;
GRANT USAGE ON SCHEMA public TO querymind_readonly;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO querymind_readonly;

-- Create a sample table for testing
CREATE TABLE IF NOT EXISTS sample_employees (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    department VARCHAR(50) NOT NULL,
    salary NUMERIC(10, 2) NOT NULL,
    hire_date DATE NOT NULL,
    is_active BOOLEAN DEFAULT true
);

INSERT INTO sample_employees (name, department, salary, hire_date, is_active) VALUES
    ('Alice Johnson', 'Engineering', 120000, '2020-01-15', true),
    ('Bob Smith', 'Engineering', 110000, '2019-06-01', true),
    ('Carol Williams', 'Marketing', 95000, '2021-03-20', true),
    ('David Brown', 'Marketing', 88000, '2020-11-10', true),
    ('Eve Davis', 'Sales', 92000, '2018-07-22', true),
    ('Frank Miller', 'Sales', 85000, '2022-01-05', true),
    ('Grace Wilson', 'Engineering', 130000, '2017-09-14', true),
    ('Henry Taylor', 'HR', 78000, '2021-08-30', true),
    ('Ivy Anderson', 'HR', 82000, '2019-04-12', false),
    ('Jack Thomas', 'Engineering', 115000, '2020-05-18', true)
ON CONFLICT DO NOTHING;

-- Grant SELECT on the sample table explicitly
GRANT SELECT ON sample_employees TO querymind_readonly;
