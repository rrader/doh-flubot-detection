rm /home/root/repository/README.md
rm -r /home/root/repository/readme_media
rm -r /home/root/repository/docs

quarto render README.qmd --to gfm --toc  --extract-media readme_media --citeproc --bibliography MyLibrary.bib
mv README.md readme_media /home/root/repository/

quarto render --to html --output-dir _public
mv _public /home/root/repository/docs
