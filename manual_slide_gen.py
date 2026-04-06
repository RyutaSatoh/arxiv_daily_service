import os
import storage
import slide_generator

USERNAME = 'ryuta'
DATE_STR = "2026-03-27"

def manual_gen():
    # Get papers for this date
    favorites = storage.get_favorites(USERNAME)
    target_papers = []
    for p in favorites:
        # Determine the paper's logical date
        p_date = p.get('list_date')
        if not p_date:
            p_date = p.get('saved_at', '').split('T')[0]
            
        if p_date == DATE_STR:
            target_papers.append(p)
    
    if not target_papers:
        print(f"No saved papers for {DATE_STR}")
        return
        
    print(f"Generating slides for {len(target_papers)} papers...")
    
    output_dir = os.path.join(storage.USERS_DIR, USERNAME, 'slides')
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        
    filename = f"slides_{DATE_STR}.pdf"
    output_path = os.path.join(output_dir, filename)
    
    extractor = slide_generator.SlideContentExtractor()
    extractor.generate_slides_for_papers(target_papers, output_path)
    print(f"Successfully generated: {output_path}")

if __name__ == "__main__":
    manual_gen()
