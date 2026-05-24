"""Pre-defined SQL query constants used by the dashboard export layer."""

BY_GEO = """
        SELECT use_tags.value, SUM(uses.amount_hkd_million) as total_amt,
               COUNT(DISTINCT use_tags.hk_ticker) as n_companies
        FROM use_tags
        JOIN uses ON use_tags.hk_ticker = uses.hk_ticker
            AND use_tags.use_id = uses.use_id
        WHERE use_tags.dimension = 'geo'
        GROUP BY use_tags.value
    """

BY_INDUSTRY_COMPANY_COUNT = """
        SELECT industry_primary, COUNT(DISTINCT hk_ticker)
        FROM companies WHERE industry_primary IS NOT NULL
        GROUP BY industry_primary
    """

BY_INDUSTRY_PARENT_BREAKDOWN = """
        SELECT companies.industry_primary, uses.parent_category,
               SUM(uses.percentage) as pct
        FROM uses JOIN companies ON uses.hk_ticker = companies.hk_ticker
        WHERE companies.industry_primary IS NOT NULL
        GROUP BY companies.industry_primary, uses.parent_category
        ORDER BY companies.industry_primary
    """

COMPANY_TAGS_INDUSTRY = """
        SELECT hk_ticker, dimension, value
        FROM company_tags WHERE dimension = 'industry'
    """

COMPANIES_LIST = """SELECT hk_ticker FROM companies"""

COMPANIES_MAX_UPDATED_AT = """SELECT MAX(updated_at) FROM companies"""

COMPANIES_OVERVIEW = """
        SELECT hk_ticker, company_name_en, listing_date, document_date,
               industry_primary, industry_source, total_net_proceeds,
               currency, needs_human_review
        FROM companies ORDER BY hk_ticker
    """

COMPANIES_ROW_COUNT = """SELECT COUNT(*) FROM companies"""

CROSS_DIM_USES = """
        SELECT c.hk_ticker, c.industry_primary,
               c.listing_date, c.total_net_proceeds,
               u.use_id, u.parent_category, u.percentage,
               u.amount_hkd_million
        FROM uses u JOIN companies c ON u.hk_ticker = c.hk_ticker
        ORDER BY c.hk_ticker, u.use_id
    """

CROSS_DIM_USE_TAGS = """
        SELECT hk_ticker, use_id, dimension, value
        FROM use_tags WHERE dimension IN (
            'geo', 'country', 'specificity', 'timeline',
            'capex_opex', 'esg_tag', 'commitment'
        )
    """

SANKEY_USES_BY_TICKER = """
        SELECT parent_category, main_category, sub_category,
               amount_hkd_million
        FROM uses WHERE hk_ticker = ? ORDER BY use_id
    """

TIME_SERIES_BY_YEAR = """
        SELECT listing_date, parent_category, SUM(percentage) as pct
        FROM uses JOIN companies ON uses.hk_ticker = companies.hk_ticker
        WHERE listing_date IS NOT NULL
        GROUP BY listing_date, parent_category
        ORDER BY listing_date
    """
