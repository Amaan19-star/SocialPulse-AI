from flask import Flask, render_template
from flask_login import login_required
import matplotlib.pyplot as plt
import os

app = Flask(__name__)

os.makedirs("static/chart", exist_ok=True)

plt.figure(figsize=(5,5))
plt.pie([3, 2, 1],
        labels=["Positive", "Negative", "Neutral"],
        autopct="%1.1f%%")

plt.savefig("static/chart/chart.png")
plt.close()

print("Chart created successfully!")
