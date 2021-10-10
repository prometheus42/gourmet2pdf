#! /usr/bin/env python3

"""
gourmet2pdf

@author: Christian Wichmann
"""


import re
import io
import json
import base64
import string
import argparse
from pathlib import Path

from bs4 import BeautifulSoup, CData
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus.doctemplate import BaseDocTemplate, PageTemplate
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import BalancedColumns, KeepTogether

PAGE_WIDTH, PAGE_HEIGHT = A4
BORDER_HORIZONTAL = 2.0*cm
BORDER_VERTICAL = 1.5*cm
PAGE_BREAK_AFTER_RECIPE = True
TITLE = 'Rezeptsammlung'
AUTHOR = 'Markus Wichmann'


class Heading(Paragraph):
    """
    Subclass for recipe headings that adds an entry in the documents outline
    shown by most PDF viewers.
    """
    def draw(self):
        super(Heading, self).draw()
        key = self.text
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(self.text, key, 0, 0)


def starify_rating(rating):
    """Creates a number of full and half stars according to the given rating."""
    rate = 0
    try:
        rate = float(rating.split('/')[0])
    except ValueError:
        print('Could not parse recipe rating: ', rating)
    full = ''.join('\uf005' * int(rate))
    half = '\uf089' if rate != int(rate) else ''
    return '<font face="FontAwesome">{}{}</font>'.format(full, half)


def create_first_page(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 16)
    canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-98, TITLE)
    canvas.setFont('Helvetica', 11)
    canvas.drawCentredString(PAGE_WIDTH/2.0, PAGE_HEIGHT-130, AUTHOR)
    canvas.setFont('Helvetica', 10)
    canvas.drawString(BORDER_HORIZONTAL, BORDER_VERTICAL, TITLE)
    canvas.drawRightString(PAGE_WIDTH-BORDER_HORIZONTAL , BORDER_VERTICAL, "Seite 1")
    canvas.restoreState()


def create_later_pages(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 10)
    canvas.drawString(BORDER_HORIZONTAL, BORDER_VERTICAL, TITLE)
    canvas.drawRightString(PAGE_WIDTH-BORDER_HORIZONTAL, BORDER_VERTICAL, "Seite {}".format(doc.page))
    canvas.restoreState()


def add_ingredients_for_group(enclosing_tag):
    ingredients_heading_style = ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, leading=10, leftIndent=8)
    ingredients_style = ParagraphStyle(name='Normal', fontName='Times-Roman', fontSize=10, leading=10, leftIndent=8)
    p = []
    if enclosing_tag.groupname:
        p.append(Paragraph(enclosing_tag.groupname.text, ingredients_heading_style))
    for i in enclosing_tag.find_all('ingredient'):
        p.append(Paragraph('{} {} {}'.format(i.amount if i.amount else '',
                                             i.unit if i.unit else '',
                                             i.item if i.item else ''), ingredients_style))
    return p


def create_pdf_doc(input_file, output_file):
    pdfmetrics.registerFont(TTFont('FontAwesome', 'font_awesome.ttf'))
    heading_style = ParagraphStyle(name='Normal', fontName='Helvetica',
                                   spaceAfter=0.25*cm, spaceBefore=0.5*cm, fontSize=15, leading=18)
    subheading_style = ParagraphStyle(name='Normal', fontName='Helvetica',
                                      spaceAfter=0.2*cm, spaceBefore=0.4*cm,fontSize=13, leading=18)
    paragraph_style = ParagraphStyle(name='Normal', fontName='Times-Roman', fontSize=11, leading=18)
    small_style = ParagraphStyle(name='Normal', fontName='Times-Roman', fontSize=8)
    doc = SimpleDocTemplate(output_file, author=AUTHOR, title=TITLE)
    story = [Spacer(1,3.5*cm)]
    link_template = '<link href="{0}" color="blue">{0}</link>'
    # create necessary building blocks for each recipe
    for recipe in parse_xml_file(input_file):
        substory = []
        recipe_heading = Heading('{}'.format(recipe.title.string), heading_style)
        substory.append(recipe_heading)

        # build block with information about the recipe
        topline = []
        if recipe.source: topline.append('Quelle: {}'.format(recipe.source.string))
        if recipe.link: topline.append('Link: {}'.format(link_template.format(recipe.link.string)))
        if recipe.rating: topline.append('Bewertung: {}'.format(starify_rating(recipe.rating.string)))
        if recipe.category: topline.append('Kategorie: {}'.format(recipe.category.string))
        substory.append(Paragraph('<br/>'.join(topline), small_style))

        # extract image if it exists
        if recipe.image:
            im = Image(io.BytesIO(base64.b64decode(recipe.image.string)))
            im._restrictSize(7*cm, 7*cm)
            im.hAlign = 'RIGHT'
        else:
            im = Paragraph('', paragraph_style)

        # extract all ingredient groups with their ingredients
        ingredient_groups = []
        # TODO: Search only in <ingredient-list> tag.
        igroup_tags = recipe.find_all('inggroup')
        if igroup_tags:
            for igroup in igroup_tags:
                ingredient_groups.append(add_ingredients_for_group(igroup))
        else:
            ingredient_groups.append(add_ingredients_for_group(recipe))
        
        # build two columns for ingredients and image (covering multiple rows!)
        substory.append(Paragraph('Zutaten', subheading_style))
        try:
            data = [ [ ingredient_groups[0][0], im ] ]
        except:
            data = [ [ Paragraph('Keine Zutaten für dieses Rezept gegeben!', paragraph_style), im ] ]
        # add remaining ingredients for first ingredients group
        for i in ingredient_groups[0][1:]:
            data.append( [i] )
        # add ingredients for all remaining ingredient groups to document
        for g in ingredient_groups[1:]:
            data.append( [Spacer(1,2*mm)])
            for i in g:
                data.append( [i] )
        # build table from list of elements
        table = Table(data, splitByRow=True)
        table.setStyle(TableStyle([('VALIGN',(0, 0),  (-1, -1), 'TOP'),
                                   ('ALIGN', (0, 0),  (0, 0),   'LEFT'),
                                           ('SPAN',  (1, 0),  (1, min(10, len(ingredient_groups[0])-1))),
                                   ('ALIGN', (-1, 0), (-1, 0),  'RIGHT')]))
        substory.append(table)
        # build text blocks for instructions and notes
        if recipe.instructions:
            substory.append(Paragraph('Anweisungen', subheading_style))
            s = recipe.instructions.string.replace('\n', '<br/>')
            substory.append(Paragraph('{}'.format(s), paragraph_style))
        if recipe.modifications:
            substory.append(Paragraph('Notizen', subheading_style))
            s = recipe.modifications.string.replace('\n', '<br/>')
            substory.append(Paragraph('{}'.format(s), paragraph_style))
        # break page after each recipe if PAGE_BREAK_AFTER_RECIPE is true
        if PAGE_BREAK_AFTER_RECIPE:
            substory.append(PageBreak())
        else:
            substory.append(Paragraph('<br/><br/><br/>', ParagraphStyle(name='Normal')))
        story = story + substory
    doc.build(story, onFirstPage=create_first_page, onLaterPages=create_later_pages)


def parse_time(time_string):
    """
    Parses time from the format:
    * 1 Stunde
    * 45 Minuten
    * 1/2 Stunden
    to the format: PT0H45M
    """
    # parse string and capture the to numbers for hours and minutes    
    regex = r"(?:(?P<hours>\d?\/?\d) Stunden?)? ?(?:(?P<minutes>\d?\/?\d) Minuten?)?"
    matches = re.finditer(regex, time_string, re.IGNORECASE)
    for m in matches:
        if m['hours'] and '/' in m['hours']:
            h1, h2 = [int(x) for x in m['hours'].split('/')]
            if m['minutes']:
                hours = 1
                minutes = (int(m['minutes']) + int(h1 / h2 * 60)) % 60
            else:
                hours = 0
                minutes = int(h1 / h2 * 60)
        else:
            hours = int(m['hours']) if m['hours'] else 0
            minutes = int(m['minutes']) if m['minutes'] else 0
        break
    return 'PT{}H{}M'.format(hours, minutes)


def create_json_doc(input_file, output_dir):
    """
    Source: https://schema.org/Recipe
    """
    base_path = Path(output_dir)
    if not base_path.is_dir or not base_path.exists:
        print('Output directory ({}) is not a directory!'.format(output_dir))
        return

    for recipe in parse_xml_file(input_file):
        # filter out all characters not suitable for the filesystem
        valid_chars = "-_.() {0}{1}äöüÄÖÜß".format(string.ascii_letters, string.digits)
        valid_dirname = "".join(ch for ch in recipe.title.string if ch in valid_chars)
        recipe_dir = base_path / valid_dirname
        try:
            recipe_dir.mkdir()
        except FileExistsError as e:
            print('Recipe already converted: {}'.format(recipe.title.string))
            continue

        recipe_data = {'@context': 'https://schema.org', '@type': 'Recipe'}
        
        recipe_data['name'] = recipe.title.string
        recipe_data['author'] = AUTHOR
        
        # TODO: Check how to store the source of the recipe correctly.
        if recipe.source: recipe_data['publisher'] = {'@type': 'Organization', 'name': recipe.source.string}
        if recipe.link: recipe_data['url'] = recipe.link.string
        if recipe.category: recipe_data['recipeCategory'] = recipe.category.string

        if recipe.rating:
            rate = 0
            try:
                rate = float(recipe.rating.string.split('/')[0]) / 5 * 10
            except ValueError:
                print('Could not parse recipe rating: ', recipe.rating)
            except TypeError:
                print('Could not parse recipe rating: ', recipe.rating)
            recipe_data['aggregateRating'] = {"@type": "AggregateRating", "ratingCount": 1, "ratingValue": str(rate)}
        
        if recipe.preptime: recipe_data['prepTime'] = parse_time(recipe.preptime.string)
        if recipe.cooktime: recipe_data['cookTime'] = parse_time(recipe.cooktime.string)
        if recipe.totalTime: recipe_data['performTime'] = parse_time(recipe.totalTime.string)
        if recipe.yields: recipe_data['recipeYield'] = recipe.yields.string

        #if recipe.image: recipe_data['image'] = 'data:image/jpeg;base64,{}'.format(recipe.image.string)
        if recipe.image:
            image_file_name = recipe_dir / 'full.jpg'
            with open(image_file_name, 'wb') as imagefile:
                imagefile.write(base64.b64decode(recipe.image.string))
            recipe_data['image'] = str(image_file_name)

        # TODO: Handle ingredient groups better (for support in Nextcloud see: https://github.com/nextcloud/cookbook/issues/311)
        ingredients = []
        igroup_tags = recipe.find_all('inggroup')
        if igroup_tags:
            for igroup in igroup_tags:
                if igroup.groupname:
                    ingredients.append('## {}'.format(igroup.groupname))
                for i in igroup.find_all('ingredient'):
                    ingredients.append('{} {} {}'.format(i.amount.string if i.amount else '', i.unit.string if i.unit else '', i.item.string if i.item else ''))
        else:
            for i in recipe.find_all('ingredient'):
                ingredients.append('{} {} {}'.format(i.amount.string if i.amount else '', i.unit.string if i.unit else '', i.item.string if i.item else ''))
        recipe_data['recipeIngredient'] = ingredients
        
        # build text blocks for instructions and notes
        if recipe.instructions and recipe.instructions.string:
            recipe_data['recipeInstructions'] = recipe.instructions.string.split('\n')
        if recipe.modifications:
            recipe_data['comment'] = recipe.modifications.string

        with open(recipe_dir / 'recipe.json', 'w') as f:
            json.dump(recipe_data, f)


def parse_xml_file(input_file):
    with open(input_file, 'r') as recipe_file:
        soup = BeautifulSoup(recipe_file.read(), 'lxml-xml')
    for recipe in soup.find_all('recipe'):
        yield recipe


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Converts recipes in the file format of Gourmet Recipe Manager to other formats.')
    parser.add_argument('input_file', help='Gourmet recipe file')
    parser.add_argument('output_file', help='Output file or directory', nargs='?', default='')
    parser.add_argument('-f', '--export_format', help='File format to convert Gourmet recipe database to', nargs=1, default='pdf', choices=['json', 'pdf'])
    args = parser.parse_args()
    if 'pdf' in args.export_format:
        create_pdf_doc(args.input_file, args.output_file if args.output_file else args.input_file+'.pdf')
    elif 'json' in args.export_format:
        create_json_doc(args.input_file, args.output_file if args.output_file else '.')
    else:
        print('Chosen file format not supported.')
