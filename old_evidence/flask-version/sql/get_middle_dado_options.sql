-- SQLite
SELECT DISTINCT category AS label FROM dado_options WHERE type = 'dado' and category LIKE '%mm%'
ORDER BY CAST(REPLACE(category, 'mm', '') AS INTEGER);