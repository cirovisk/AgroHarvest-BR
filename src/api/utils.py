from sqlalchemy import func


def paginate_query(query, page: int, page_size: int):
    # Validate bounds and safety limits to avoid DoS and errors
    if page < 1:
        page = 1
    if page_size < 1:
        page_size = 10
    elif page_size > 100:
        page_size = 100

    # Use an optimized COUNT subquery to avoid re-running the full main query
    total = query.with_entities(func.count()).order_by(None).scalar()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

    return {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages, "items": items}
