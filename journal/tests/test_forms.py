from journal.forms import EntryForm

def test_entry_form_has_images_and_tabs():
    f = EntryForm()
    assert "images" in f.fields and "tabs" in f.fields
    # multiple file input enabled
    assert getattr(f.fields["images"].widget, "allow_multiple_selected", False) is True