from app.scraper import _parse_ungm_notice_rows, _ungm_search_payload


def test_parse_ungm_notice_rows_extracts_structured_fields():
    html = """
    <div role="row" tabindex="0" data-noticeid="299816" class="tableRow dataRow notice-table">
      <div role="cell" class="tableCell editable intendbuttonsHeader resultOptions"></div>
      <div role="cell" class="tableCell resultTitle">
        Call for External Collaborator - Workflow Records System
        <a href="/Public/Notice/299816">Open in a new window</a>
      </div>
      <div role="cell" class="tableCell resultInfo1 deadline">
        13-May-2099 11:00 (GMT 2.00) 8.12135134834143
      </div>
      <div role="cell" class="tableCell">05-May-2099</div>
      <div role="cell" class="tableCell resultAgency">ILO</div>
      <div role="cell" class="tableCell">Request for proposal</div>
      <div role="cell" class="tableCell resultInfo1">RFP-ILO-2099-001</div>
      <div role="cell" class="tableCell">Uganda</div>
    </div>
    """

    notices = _parse_ungm_notice_rows(html)

    assert len(notices) == 1
    notice = notices[0]
    assert notice["notice_id"] == "299816"
    assert notice["title"] == "Call for External Collaborator - Workflow Records System"
    assert notice["link"] == "https://www.ungm.org/Public/Notice/299816"
    assert notice["deadline"] == "2099-05-13"
    assert notice["publication_date"] == "2099-05-05"
    assert notice["buyer"] == "ILO"
    assert notice["country"] == "Uganda"
    assert "RFP-ILO-2099-001" in notice["description"]


def test_ungm_search_payload_scans_all_un_agencies_by_default():
    payload = _ungm_search_payload(description="records management")

    assert payload["Description"] == "records management"
    assert payload["Agencies"] == []
    assert payload["Countries"] == []
    assert payload["IsActive"] is True
    assert payload["SortField"] == "DatePublished"
