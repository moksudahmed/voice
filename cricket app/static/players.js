const slides =
document.querySelectorAll(".team-slide");

const dots =
document.querySelectorAll(".dot");

let current = 0;

function showSlide(index){

    slides.forEach((slide,i)=>{

        slide.classList.remove("active");

        dots[i].classList.remove("active");

        if(i === index){

            slide.classList.add("active");

            dots[i].classList.add("active");
        }
    });
}

/* =========================================================
AUTO SLIDE
========================================================= */

setInterval(()=>{

    current++;

    if(current >= slides.length){

        current = 0;
    }

    showSlide(current);

},7000);

/* =========================================================
DOT CLICK
========================================================= */

dots.forEach((dot,index)=>{

    dot.addEventListener("click",()=>{

        current = index;

        showSlide(current);
    });
});