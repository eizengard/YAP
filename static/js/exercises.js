const exercises = [
    {
        id: 'vocab-1',
        type: 'vocabulary',
        words: ['hello', 'goodbye', 'thank you', 'please'],
        translations: ['hola', 'adiós', 'gracias', 'por favor']
    },
    {
        id: 'grammar-1',
        type: 'grammar',
        sentences: ['I am learning Spanish', 'She speaks English'],
        correct: ['Estoy aprendiendo español', 'Ella habla inglés']
    }
];

let currentExercise = 0;
let score = 0;

function loadExercise() {
    const exercise = exercises[currentExercise];
    const exerciseContainer = document.getElementById('exercise-container');
    exerciseContainer.innerHTML = '';

    if (exercise.type === 'vocabulary') {
        createVocabExercise(exercise);
    } else if (exercise.type === 'grammar') {
        createGrammarExercise(exercise);
    }
}

function createVocabExercise(exercise) {
    const container = document.getElementById('exercise-container');
    exercise.words.forEach((word, index) => {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${word}</h5>
                <input type="text" class="form-control" placeholder="Enter translation">
                <button class="btn btn-primary mt-2" onclick="checkVocabAnswer(${index})">Check</button>
            </div>
        `;
        container.appendChild(card);
    });
}

function createGrammarExercise(exercise) {
    const container = document.getElementById('exercise-container');
    exercise.sentences.forEach((sentence, index) => {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${sentence}</h5>
                <input type="text" class="form-control" placeholder="Enter translation">
                <button class="btn btn-primary mt-2" onclick="checkGrammarAnswer(${index})">Check</button>
            </div>
        `;
        container.appendChild(card);
    });
}

async function saveProgress() {
    try {
        const response = await fetch('/api/save-progress', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exercise_id: exercises[currentExercise].id,
                score: score
            }),
        });

        if (!response.ok) {
            throw new Error('Failed to save progress');
        }
    } catch (error) {
        console.error('Progress save error:', error);
    }
}

document.addEventListener('DOMContentLoaded', loadExercise);
