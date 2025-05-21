// function updateCategories() {
//     const type = document.getElementById('type').value;
//     fetch(`/get_categories?type=${type}`)
//         .then(response => response.json())
//         .then(data => {
//             const categorySelect = document.getElementById('category');
//             categorySelect.innerHTML = '';
            
//             data.categories.forEach(cat => {
//                 const option = document.createElement('option');
//                 option.value = cat.id;
//                 option.text = cat.name;
//                 categorySelect.appendChild(option);
//             });
//         });
// }

// function toggleNewCategory() {
//     const field = document.getElementById('newCategoryField');
//     field.style.display = field.style.display === 'none' ? 'block' : 'none';
// }


// document.addEventListener('DOMContentLoaded', function() {
//     updateCategories();
    

//     document.querySelector('a[onclick="toggleNewCategory()"]')
//         .addEventListener('click', toggleNewCategory);
// });