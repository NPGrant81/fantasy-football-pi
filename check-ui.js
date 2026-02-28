const fs = require("fs");
const path = require("path");

const directory = "./src";
const responsivePrefixes = ["sm:", "md:", "lg:", "xl:"];

function checkFiles(dir) {
  const files = fs.readdirSync(dir);
  files.forEach((file) => {
    const filePath = path.join(dir, file);
    if (fs.statSync(filePath).isDirectory()) {
      checkFiles(filePath);
    } else if (file.endsWith(".jsx")) {
      const content = fs.readFileSync(filePath, "utf8");
      const hasResponsive = responsivePrefixes.some((p) => content.includes(p));
      if (!hasResponsive) {
        console.log(`❌ Missing Breakpoints: ${filePath}`);
      }
    }
  });
}

checkFiles(directory);
