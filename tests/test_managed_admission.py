from perfagent.contracts.load_model import LoadModel
from perfagent.runner.admission import admission_checks


def test_managed_admission_requires_exact_origin_and_bounded_request_rate():
    model = LoadModel.model_validate({
        "target_base_url": "https://api.example.test:443/staging",
        "scenarios": [{"name": "browse", "steps": [{"name": "products", "path": "/products"}]}],
        "load_profile": {"stages": [{"duration_seconds": 30, "target_users": 0}],
                         "arrival_rate": 10, "target_request_rate": 10,
                         "pre_allocated_vus": 5, "graceful_stop_seconds": 5},
    })
    approved = ["https://api.example.test"]
    limits = {"max_vus": 5, "max_seconds": 35, "max_requests_per_second": 10}
    metadata = {"generated": True}

    def checks():
        return [entry["ok"] for entry in admission_checks(model, metadata, approved, **limits)]

    assert checks() == [True, True, True]
    model.target_base_url = "https://api.example.test:8443"
    assert checks() == [False, True, True]
    model.target_base_url = "https://api.example.test"
    model.insecure_tls = True
    metadata["script_edited"] = True
    model.load_profile.graceful_stop_seconds = 6
    assert checks() == [False, False, False]
    model.insecure_tls = False
    model.load_profile.graceful_stop_seconds = 5
    model.load_profile.pre_allocated_vus = 6
    assert checks() == [True, False, False]
