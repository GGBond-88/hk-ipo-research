"""Unit tests for src/hk_ipo/enrichments/esg_tag.py."""

from __future__ import annotations


def test_dimension_and_version():
    from hk_ipo.enrichments.esg_tag import DIMENSION, VERSION

    assert DIMENSION == "esg_tag"
    assert isinstance(VERSION, int)


def test_green_renewable_energy():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Invest in solar panel manufacturing and wind energy projects.",
        "category_raw": "renewable energy investment",
        "source_text": "We will invest in solar panel and wind energy.",
    }
    tags = classify_esg(item)
    assert "green" in tags


def test_social_healthcare():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Build affordable healthcare clinics in rural areas.",
        "category_raw": "healthcare expansion",
        "source_text": "Expanding affordable healthcare access.",
    }
    tags = classify_esg(item)
    assert "social" in tags


def test_governance_compliance():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Implement company-wide compliance and risk management systems.",
        "category_raw": "compliance systems",
        "source_text": "Strengthening compliance and governance frameworks.",
    }
    tags = classify_esg(item)
    assert "governance" in tags


def test_multiple_tags():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Green affordable housing project with governance oversight.",
        "category_raw": "sustainable affordable housing",
        "source_text": "Building green affordable housing with strong governance.",
    }
    tags = classify_esg(item)
    assert "green" in tags
    assert "social" in tags
    assert "governance" in tags


def test_no_esg_tag():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "General corporate purposes.",
        "category_raw": "general corporate purposes",
        "source_text": "For general corporate purposes.",
    }
    tags = classify_esg(item)
    assert tags == []


def test_all_three_tags_simultaneously():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": (
            "Green renewable energy projects with social inclusion "
            "and strong governance oversight."
        ),
        "category_raw": "ESG investment",
        "source_text": "Investing in green energy, social inclusion, and governance frameworks.",
    }
    tags = classify_esg(item)
    assert "green" in tags
    assert "social" in tags
    assert "governance" in tags


def test_empty_item_dict():
    from hk_ipo.enrichments.esg_tag import classify_esg

    tags = classify_esg({})
    assert tags == []


def test_none_field_values():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": None,
        "category_raw": None,
        "source_text": None,
    }
    tags = classify_esg(item)
    assert tags == []


def test_case_insensitivity():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "SOLAR and WIND energy investment.",
        "category_raw": "HEALTHCARE expansion",
        "source_text": "Strengthening GOVERNANCE and COMPLIANCE frameworks.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "should match uppercase SOLAR/WIND"
    assert "social" in tags, "should match uppercase HEALTHCARE"
    assert "governance" in tags, "should match uppercase GOVERNANCE/COMPLIANCE"


def test_green_stem_energy_efficiency():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Investing in energy efficiency improvements.",
        "category_raw": "energy efficiency",
        "source_text": "Energy efficiency retrofit program.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "energy efficiency stem should match green"


def test_green_stem_energy_efficient():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Deploying energy efficient technologies.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "energy efficient stem should match green"


def test_green_stem_decarbonization():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Decarbonization of our supply chain.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "decarbonization stem should match green"


def test_green_stem_decarbonising():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Decarbonising operations across all sites.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "decarbonising stem should match green"


def test_green_stem_decarbonizes():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Company decarbonizes its manufacturing process.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "decarbonizes (3rd person singular US) stem should match green"


def test_green_stem_decarbonises():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Company decarbonises its supply chain.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "decarbonises (3rd person singular UK) stem should match green"


def test_social_stem_charity():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Supporting local charity initiatives.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "charity stem should match social"


def test_social_stem_charitable():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Charitable donations to community organizations.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "charitable stem should match social"


def test_social_stem_philanthropy():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Corporate philanthropy program.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "philanthropy stem should match social"


def test_social_stem_philanthropic():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Philanthropic activities in underserved areas.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "philanthropic stem should match social"


def test_missing_use_id_no_key_error():
    import shutil
    import tempfile
    from pathlib import Path

    from hk_ipo.enrichments.esg_tag import _enrich_one

    record = {
        "hk_ticker": "TEST01",
        "uses": [
            {"description": "solar panels", "category_raw": "", "source_text": ""},
            {"use_id": "u2", "description": "general corp", "category_raw": "", "source_text": ""},
        ],
    }
    enriched_dir = Path(tempfile.mkdtemp())
    try:
        _enrich_one(record, enriched_dir)
    except KeyError:
        assert False, "should not raise KeyError for missing use_id"
    finally:
        shutil.rmtree(enriched_dir, ignore_errors=True)


# CR-014: plural/inflected forms that were broken by \b boundary
def test_green_emissions_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Reducing emissions from operations.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "emissions (plural) should match green"


def test_green_recycle_verb():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "We recycle materials.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "recycle (verb) should match green"


def test_green_recycled_adjective():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Using recycled materials in packaging.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "recycled (adjective) should match green"


def test_green_recycles_verb():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "The facility recycles products.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "recycles (third person singular verb) should match green"


def test_social_patients_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Providing care for patients.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "patients (plural) should match social"


def test_social_hospitals_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Building new hospitals.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "hospitals (plural) should match social"


def test_social_schools_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Funding public schools.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "schools (plural) should match social"


def test_social_clinics_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Establishing clinics.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "clinics (plural) should match social"


def test_social_universities_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Partnering with universities.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "universities (plural) should match social"


# SR-001: plural/inflected forms still blocked by \b boundary
def test_green_electric_vehicles_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Investing in electric vehicles.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "electric vehicles (plural) should match green"


def test_green_environments_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Protecting environments across regions.",
    }
    tags = classify_esg(item)
    assert "green" in tags, "environments (plural) should match green"


def test_social_communities_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Supporting local communities.",
    }
    tags = classify_esg(item)
    assert "social" in tags, "communities (plural) should match social"


def test_governance_audits_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Conducting external audits.",
    }
    tags = classify_esg(item)
    assert "governance" in tags, "audits (plural) should match governance"


def test_governance_internal_controls_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Strengthening internal controls.",
    }
    tags = classify_esg(item)
    assert "governance" in tags, "internal controls (plural) should match governance"


def test_governance_shareholder_rights_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Protecting shareholder rights.",
    }
    tags = classify_esg(item)
    assert "governance" in tags, "shareholder rights (plural) should match governance"


def test_governance_whistleblowers_plural():
    from hk_ipo.enrichments.esg_tag import classify_esg

    item = {
        "description": "Protecting whistleblowers.",
    }
    tags = classify_esg(item)
    assert "governance" in tags, "whistleblowers (plural) should match governance"
