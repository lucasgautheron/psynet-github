"""Empty PsyNet experiment scaffold for {{project_title}}."""

import psynet.experiment
from psynet.consent import NoConsent
from psynet.page import InfoPage, SuccessfulEndPage
from psynet.timeline import Timeline


class Exp(psynet.experiment.Experiment):
    label = "{{project_title}}"
    test_n_bots = 1

    timeline = Timeline(
        NoConsent(),
        InfoPage(
            "Welcome to this PsyNet experiment scaffold. Replace this page "
            "with your experiment instructions and trials.",
            time_estimate=5,
        ),
        SuccessfulEndPage(),
    )
