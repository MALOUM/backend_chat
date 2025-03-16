from motor.motor_asyncio import AsyncIOMotorClient
import asyncio

async def main():
    client = AsyncIOMotorClient('mongodb://localhost:27017')
    db = client['chat_db']
    coll = db['chat_sessions']
    session = await coll.find_one()
    print("Structure d'une session dans MongoDB:")
    print(session)

if __name__ == "__main__":
    asyncio.run(main()) 