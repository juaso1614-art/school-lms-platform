/* Generates colourful floating flowers behind every page */
(function () {
  var flowers = ["🌸", "🌺", "🌻", "🌼", "🌷", "🌹", "💐", "🏵️"];
  var animations = ["", "spin", "drift"];
  var bg = document.createElement("div");
  bg.className = "flower-bg";
  var count = 28;

  for (var i = 0; i < count; i++) {
    var petal = document.createElement("span");
    petal.className = "petal " + animations[i % animations.length];
    petal.textContent = flowers[i % flowers.length];
    petal.style.left = (Math.random() * 100) + "%";
    petal.style.top = (Math.random() * 100) + "%";
    petal.style.fontSize = (1.2 + Math.random() * 2.8).toFixed(1) + "rem";
    petal.style.setProperty("--dur", (12 + Math.random() * 25).toFixed(0) + "s");
    petal.style.setProperty("--delay", "-" + (Math.random() * 20).toFixed(1) + "s");
    bg.appendChild(petal);
  }

  document.body.prepend(bg);
})();
