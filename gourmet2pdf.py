
"""
gourmet2pdf

@author: Christian Wichmann
"""


import io
import base64

from bs4 import BeautifulSoup, CData
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, Table, TableStyle
from reportlab.platypus.flowables import KeepTogether, BalancedColumns
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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
        # build two columns with ingredients and image
        p = [ Paragraph('{} {} {}'.format(i.amount if i.amount else '',
                                          i.unit if i.unit else '',
                                          i.item if i.item else ''), paragraph_style)
              for i in recipe.find_all('ingredient') ]
        if recipe.image:
            im = Image(io.BytesIO(base64.b64decode(recipe.image.string)))
            im._restrictSize(7*cm, 7*cm)
            im.hAlign = 'RIGHT'
        else:
            im = Paragraph('', paragraph_style)
        substory.append(Paragraph('Zutaten', subheading_style))
        data = [ [ p, im ] ]
        table = Table(data, splitByRow=True)
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                   ('ALIGN',(0,0),(0,0),'LEFT'),
                                   ('ALIGN',(-1,0),(-1,0),'RIGHT')]))
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


def parse_xml_file(input_file):
    with open(input_file, 'rb') as recipe_file:
        soup = BeautifulSoup(recipe_file.read(), 'lxml-xml')
    for recipe in soup.find_all('recipe'):
        yield recipe


if __name__ == '__main__':
    output_file = '/home/christian/Desktop/gourmet2pdf/Rezepte.grmt.pdf'
    input_file = '/home/christian/Desktop/gourmet2pdf/Rezepte.grmt'
    create_pdf_doc(input_file, output_file)
