# gourmet2pdf
Converts recipes from Gourmet file format to other file formats, including PDF and JSON.

## Usage
To convert a recipe file to PDF file:

    ./gourmet2pdf.py recipes.grmt

To create a JSON file for use in Nextcloud Cookbook use the command:

    ./gourmet2pdf.py recipes.grmt output_dir/ -f json

## Requirements
* Reportlab library for creating PDF files 
* BeautifulSoup library for parsing XML files
* lxml installed in the system as parser for BeautifulSoup
* Font Awesome for rating symbols under the Font Awesome Free License
