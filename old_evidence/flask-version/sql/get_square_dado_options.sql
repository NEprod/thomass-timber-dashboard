-- SQLite
SELECT label_or_category
FROM (
  SELECT category AS label_or_category, 0 AS sort_order
  FROM dado_options
  WHERE type = 'dado' AND category IN ('45mm', '70mm')

  UNION

  SELECT label AS label_or_category, 1 AS sort_order
  FROM dado_options
  WHERE type = 'moulding' AND category IN ('astragal', 'decorative_cover')
)
ORDER BY sort_order ASC, label_or_category ASC;