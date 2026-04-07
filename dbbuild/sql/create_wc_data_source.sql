CREATE TABLE IF NOT EXISTS data_source_info (
    id serial PRIMARY KEY,
    name varchar(200) NOT NULL UNIQUE,
    description text,
    source_url text,
    download_url text,
    dict_url text,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);
