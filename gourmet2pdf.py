
"""
gourmet2pdf

@author: Christian Wichmann
"""


import io
import base64
import tempfile
import datetime

from bs4 import BeautifulSoup, CData
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.units import cm, mm
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus.doctemplate import PageTemplate, BaseDocTemplate
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, PageBreak, LongTable, Table, TableStyle
from reportlab.platypus.flowables import KeepTogether, BalancedColumns


PAGE_WIDTH, PAGE_HEIGHT = A4
BORDER_HORIZONTAL = 2.0*cm
BORDER_VERTICAL = 1.5*cm
PAGE_BREAK_AFTER_RECIPE = True
TODAY = datetime.datetime.today().strftime('%d.%m.%Y')
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
    heading_style = ParagraphStyle(name='Normal', fontName='Helvetica',
                                   spaceAfter=0.25*cm, spaceBefore=0.5*cm, fontSize=15, leading=18)
    subheading_style = ParagraphStyle(name='Normal', fontName='Helvetica',
                                      spaceAfter=0.2*cm, spaceBefore=0.4*cm,fontSize=13, leading=18)
    paragraph_style = ParagraphStyle(name='Normal', fontName='Times-Roman', fontSize=11, leading=18)
    small_style = ParagraphStyle(name='Normal', fontName='Times-Roman', fontSize=8)
    doc = SimpleDocTemplate(output_file, author=AUTHOR, title=TITLE)
    story = [Spacer(1,3.5*cm)]
    #
    for recipe in parse_xml_file(input_file):
        substory = []
        recipe_heading = Heading('{}'.format(recipe.title.string), heading_style)
        substory.append(recipe_heading)
        #
        topline = []
        if recipe.source: topline.append('Quelle: {}'.format(recipe.source.string))
        if recipe.link: topline.append('Link: {}'.format(recipe.link.string))
        if recipe.rating: topline.append('Bewertung: {}'.format(recipe.rating.string))
        if recipe.category: topline.append('Kategorie: {}'.format(recipe.category.string))
        substory.append(Paragraph('<br/>'.join(topline), small_style))
        # build two columns with ingredients and image
        p = [ Paragraph('{} {} {}'.format(i.amount if i.amount else '',
                                          i.unit if i.unit else '',
                                          i.item if i.item else ''), paragraph_style)
              for i in recipe.find_all('ingredient') ]
        im = Paragraph('', paragraph_style)       
        for cd in recipe.findAll(text=True):
            # TODO: Check for image format (recipe.image['format']).
            if isinstance(cd, CData):
                im = Image(io.BytesIO(base64.b64decode(cd)), width=5*cm, height=5*cm)
                im.hAlign = 'RIGHT'
                break
        data = [ [ [Paragraph('Zutaten', subheading_style)] + p, im ] ]
        table = Table(data, colWidths=[10*cm, 6*cm], splitByRow=True)
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                                   ('ALIGN',(0,0),(-1,-1),'LEFT'),
                                   ('INNERGRID', (0,0), (-1,-1), 0.25, colors.white),
                                   ('BOX', (0,0), (-1,-1), 0.25, colors.white)]))
        substory.append(table)
        #
        if recipe.instructions:
            substory.append(Paragraph('Anweisungen', subheading_style))
            s = recipe.instructions.string.replace('\n', '<br/>')
            substory.append(Paragraph('{}'.format(s), paragraph_style))
        if recipe.modifications:
            substory.append(Paragraph('Notizen', subheading_style))
            s = recipe.modifications.string.replace('\n', '<br/>')
            substory.append(Paragraph('{}'.format(s), paragraph_style))
        #
        if PAGE_BREAK_AFTER_RECIPE:
            substory.append(PageBreak())
        else:
            substory.append(Paragraph('<br/><br/><br/>', ParagraphStyle(name='Normal')))
        story = story + substory
    doc.build(story, onFirstPage=create_first_page, onLaterPages=create_later_pages)


def parse_xml_file(input_file):
    # TODO: replace source and link tags with some *valid* tag names!
    with open(input_file, 'rb') as recipe_file:
        soup = BeautifulSoup(recipe_file.read(), 'lxml-xml') #'html.parser')
    for nr, recipe in enumerate(soup.find_all('recipe')):
        yield recipe


if __name__ == '__main__':
    output_file = '/home/christian/Desktop/gourmet2pdf/Rezepte.grmt.pdf'
    input_file = '/home/christian/Desktop/gourmet2pdf/Rezepte.grmt'
    create_pdf_doc(input_file, output_file)
