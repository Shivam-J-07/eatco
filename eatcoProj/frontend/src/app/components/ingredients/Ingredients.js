import React, { useState } from 'react';
import './Ingredients.css';

function Ingredients(props) {

  const {
    ingredients,
  } = props;

  return (
    <div className="Ingredients">
      <h2>Ingredients</h2>
        {ingredients.map(ingredient => 
            <div key={ingredient.index}>
                <input type="checkbox" />
                <label>{ingredient}</label><br></br>
            </div>
        )}
    </div>
  );
}
  
export default Ingredients;
  