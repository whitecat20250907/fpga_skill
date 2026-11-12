from core.console_auth import console_token


def test_pairing_survives_runtime_cleanup_and_migrates_existing_token(tmp_path):
    run=tmp_path/'run';run.mkdir();persistent=tmp_path/'state/token'
    previous='existing-console-pairing-token-123456789'
    (run/'console.token').write_text(previous)
    assert console_token(run,persistent)==previous
    (run/'console.token').unlink()
    assert console_token(run,persistent)==previous
    assert (run/'console.token').read_text()==previous
    assert persistent.stat().st_mode & 0o777 == 0o600
