let questions = [];

let currentQuestionIndex = 0;

let totalScore = 0;

let answered = false;


// ------------------------------------
// ANSWER NORMALIZATION
// ------------------------------------

function normalizeAnswer(text) {

    return text

        .toLowerCase()

        .trim()

        // remove accents
        .normalize("NFD")

        .replace(
            /[\u0300-\u036f]/g,
            ""
        )

        // turn & into "and"
        .replace(
            /&/g,
            "and"
        )

        // remove punctuation
        .replace(
            /[^a-z0-9\s]/g,
            ""
        )

        // remove beginning:
        // the / a / an
        .replace(
            /^(the|a|an)\s+/,
            ""
        )

        // remove extra spaces
        .replace(
            /\s+/g,
            " "
        );

}


// ------------------------------------
// SHUFFLE QUESTIONS
// ------------------------------------

function shuffle(array) {

    for (
        let i = array.length - 1;
        i > 0;
        i--
    ) {

        const j =
            Math.floor(
                Math.random() *
                (i + 1)
            );


        [
            array[i],
            array[j]
        ]

        =

        [
            array[j],
            array[i]
        ];

    }

}


// ------------------------------------
// LOAD QUESTION DATABASE
// ------------------------------------

async function loadQuestions() {

    try {

        const response =
            await fetch(
                "data/questions.json"
            );


        if (!response.ok) {

            throw new Error(
                "Could not load database"
            );

        }


        questions =
            await response.json();


        shuffle(questions);


        showQuestion();

    }

    catch (error) {

        document
            .getElementById("question")
            .textContent =
                "Could not load questions.";

        console.error(error);

    }

}


// ------------------------------------
// DISPLAY QUESTION
// ------------------------------------

function showQuestion() {

    answered = false;


    const question =
        questions[currentQuestionIndex];


    document
        .getElementById("question")
        .textContent =
            question.question;


    document
        .getElementById("question-number")
        .textContent =
            `Question ${
                currentQuestionIndex + 1
            } / ${questions.length}`;


    const input =
        document.getElementById(
            "answer-input"
        );


    input.value = "";

    input.disabled = false;

    input.focus();


    document
        .getElementById("result")
        .textContent = "";


    document
        .getElementById("next-button")
        .hidden = true;

}


// ------------------------------------
// FIND ANSWER
// ------------------------------------

function findAnswer(playerInput) {

    const playerAnswer =
        normalizeAnswer(playerInput);


    const question =
        questions[currentQuestionIndex];


    for (
        const answer
        of question.answers
    ) {

        // Main name

        if (
            normalizeAnswer(answer.name)
            === playerAnswer
        ) {

            return answer;

        }


        // Aliases

        for (
            const alias
            of answer.aliases
        ) {

            if (
                normalizeAnswer(alias)
                === playerAnswer
            ) {

                return answer;

            }

        }

    }


    return null;

}


// ------------------------------------
// SUBMIT ANSWER
// ------------------------------------

document
    .getElementById("answer-form")
    .addEventListener(
        "submit",
        function(event) {

            event.preventDefault();


            if (answered) {

                return;

            }


            const input =
                document.getElementById(
                    "answer-input"
                );


            const playerInput =
                input.value;


            if (!playerInput.trim()) {

                return;

            }


            const answer =
                findAnswer(playerInput);


            const resultBox =
                document.getElementById(
                    "result"
                );


            if (answer) {

                totalScore +=
                    answer.score;


                resultBox.textContent =
                    `✓ ${answer.name} — ${answer.score} points`;

            }

            else {

                resultBox.textContent =
                    "✗ Not accepted";

            }


            answered = true;

            input.disabled = true;


            document
                .getElementById("score")
                .textContent =
                    `Score: ${totalScore}`;


            document
                .getElementById(
                    "next-button"
                )
                .hidden = false;

        }
    );


// ------------------------------------
// NEXT QUESTION
// ------------------------------------

document
    .getElementById("next-button")
    .addEventListener(
        "click",
        function() {

            currentQuestionIndex++;


            if (
                currentQuestionIndex
                >= questions.length
            ) {

                finishGame();

                return;

            }


            showQuestion();

        }
    );


// ------------------------------------
// FINISH GAME
// ------------------------------------

function finishGame() {

    document
        .getElementById("question-number")
        .textContent = "";


    document
        .getElementById("question")
        .textContent =
            "Dive Complete";


    document
        .getElementById("result")
        .textContent =
            `Final score: ${totalScore}`;


    document
        .getElementById("answer-form")
        .hidden = true;


    document
        .getElementById("next-button")
        .hidden = true;

}


// ------------------------------------
// START
// ------------------------------------

loadQuestions();
