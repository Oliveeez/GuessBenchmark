document.addEventListener("DOMContentLoaded", function () {
    const scriptTag = document.querySelector('script[data-json]');
    const jsonFile = scriptTag.getAttribute('data-json');
    const imageBasePath = scriptTag.getAttribute('img-path');

    fetch(jsonFile)
        .then(response => response.json())
        .then(data => {
            renderTable(data, imageBasePath);
        })
        .catch(error => console.error('Error loading JSON data:', error));
});

function renderTable(data, imageBasePath) {
    const tbody = document.querySelector('#data-table tbody');
    tbody.innerHTML = '';

    data.forEach(item => {
        const row = document.createElement('tr');

        // Image column
        const imgCell = document.createElement('td');
        const img = document.createElement('img');
        img.src = imageBasePath + item.image_name; 
        img.alt = item.image_name;
        img.style.maxWidth = "150px"; 
        imgCell.appendChild(img);
        row.appendChild(imgCell);

        // GT column
        const gtCell = document.createElement('td');
        gtCell.textContent = item.gt;
        row.appendChild(gtCell);

        // Prediction column
        const predictionCell = document.createElement('td');
        predictionCell.textContent = item.pred;
        row.appendChild(predictionCell);

        // Inference Chain column
        const inferenceCell = document.createElement('td');
        inferenceCell.textContent = item["inference chain"];
        row.appendChild(inferenceCell);

        tbody.appendChild(row);
    });
}