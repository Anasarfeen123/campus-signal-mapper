const express = require("express");

const app = express();
app.use(express.json());

app.post("/data", async (req, res) => {
  try {
    const response = await fetch("https://vitc-signal-mapper.onrender.com/api", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.text();
    res.send(data);

  } catch (err) {
    console.log(err);
    res.status(500).send("Error");
  }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Proxy running on port ${PORT}`));