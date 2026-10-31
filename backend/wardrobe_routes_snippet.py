def _item_out(item: models.ClothingItem) -> dict:
    return {
        "id": item.id,
        "image_url": storage.image_url(item.image_filename),
        "category": item.category,
        "colour": item.colour,
        "pattern": item.pattern,
        "season": item.season,
    }


@app.post("/api/wardrobe", status_code=201)
async def add_clothing_item(
    file: UploadFile = File(...),
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not (file.content_type or "").startswith("image/"):
        raise HTTPException(status_code=400, detail="Please upload an image file.")

    data = await file.read()
    if len(data) > 15 * 1024 * 1024:  # 15 MB, before compression
        raise HTTPException(status_code=400, detail="Image is too large.")
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")

    try:
        traits = ai_identify.identify_clothing(data, file.content_type)
        filename = storage.save_image(data, user.email)
    except Exception:
        raise HTTPException(status_code=400, detail="That file doesn't look like a valid image.")

    item = models.ClothingItem(
        user_id=user.id,
        image_filename=filename,
        category=traits["category"],
        colour=traits["colour"],
        pattern=traits["pattern"],
        season=traits["season"],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _item_out(item)


@app.get("/api/wardrobe")
def list_wardrobe(user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    items = db.scalars(
        select(models.ClothingItem)
        .where(models.ClothingItem.user_id == user.id)
        .order_by(models.ClothingItem.created_at.desc())
    ).all()
    return [_item_out(item) for item in items]


def _get_owned_item(item_id: int, user: models.User, db: Session) -> models.ClothingItem:
    item = db.get(models.ClothingItem, item_id)
    if not item or item.user_id != user.id:
        raise HTTPException(status_code=404, detail="Item not found.")
    return item


@app.get("/api/wardrobe/{item_id}")
def get_clothing_item(item_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _item_out(_get_owned_item(item_id, user, db))


class UpdateItemRequest(BaseModel):
    category: str
    colour: str
    pattern: str
    season: str


@app.put("/api/wardrobe/{item_id}")
def update_clothing_item(
    item_id: int,
    body: UpdateItemRequest,
    user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = _get_owned_item(item_id, user, db)
    for field, allowed in (
        ("category", models.CATEGORIES),
        ("colour", models.COLOURS),
        ("pattern", models.PATTERNS),
        ("season", models.SEASONS),
    ):
        if getattr(body, field) not in allowed:
            raise HTTPException(status_code=400, detail=f"'{getattr(body, field)}' is not a valid {field}.")

    item.category, item.colour, item.pattern, item.season = body.category, body.colour, body.pattern, body.season
    db.commit()
    return _item_out(item)


@app.delete("/api/wardrobe/{item_id}")
def delete_clothing_item(item_id: int, user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = _get_owned_item(item_id, user, db)
    storage.delete_image(item.image_filename)
    db.delete(item)
    db.commit()
    return {"message": "Item deleted."}
