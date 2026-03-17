// WakeUpModal -- fullscreen loading when server is waking up (cold start)
import { useState, useEffect } from 'react'
import { subscribe } from './coldStartStore'

const WAKE_UP_QUOTES = [
  'The only worthless asset is the one that is valued correctly',
  'Markets can remain irrational longer than you can remain solvent',
  'Risk only comes from not knowing what you are doing',
  'The stock market is a device for transferring money from the impatient to the patient',
  'Price is what you pay. Value is what you get',
  'Be fearful when others are greedy, and greedy when others are fearful',
  'It is not whether you are right or wrong that matters, but how much money you make when right and how much you lose when wrong',
  'In the short run, the market is a voting machine. In the long run, it is a weighing machine',
  'Never test the depth of the river with both feet',
  'When life gives you lemons, backtest them on different symbols and see if you can make lemonade',
]

function getRandomQuote() {
  return WAKE_UP_QUOTES[Math.floor(Math.random() * WAKE_UP_QUOTES.length)]
}

export function WakeUpModal() {
  const [show, setShow] = useState(false)
  const [quote, setQuote] = useState(getRandomQuote)

  useEffect(() => {
    return subscribe((visible) => {
      setShow(visible)
      if (visible) setQuote(getRandomQuote())
    })
  }, [])

  if (!show) return null

  return (
    <div className="wake-up-modal">
      <div className="wake-up-modal-content">
        <h2 className="wake-up-modal-title">Waking up server</h2>
        <div className="wake-up-modal-spinner" />
        <p className="wake-up-modal-quote">{quote}</p>
      </div>
    </div>
  )
}
